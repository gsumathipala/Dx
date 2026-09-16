"""Authenticating, scoping and rate-limiting API calls.

A request presents ``Authorization: Bearer <key_id>.<secret>``. The key id
identifies the client in one indexed lookup; the secret is then checked against
a password hash, so a leaked database gives an attacker nothing usable.

Everything a client does is attributed to it in the audit trail — events show
``api:<client name>`` as the actor, not ``system`` — and every PHI read is
additionally recorded against HIPAA disclosure accounting, because sending a
patient's results to an external system is a disclosure whether a person or a
program asked for it.
"""
from __future__ import annotations

import functools
import hmac
import logging
import time

from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.api.models import PHI_SCOPES, ApiClient

logger = logging.getLogger("dx.api")


class ApiError(Exception):
    """An error with an HTTP status and a stable machine-readable code."""

    def __init__(self, status: int, code: str, message: str, **extra):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra

    def response(self) -> JsonResponse:
        body = {"error": {"code": self.code, "message": self.message, **self.extra}}
        response = JsonResponse(body, status=self.status)
        if self.status == 401:
            response["WWW-Authenticate"] = 'Bearer realm="Dx"'
        return response


def _client_ip(request) -> str | None:
    from apps.audit.context import client_ip

    return client_ip(request)


def authenticate(request) -> ApiClient:
    """Resolve the bearer token to a usable client, or raise ApiError."""
    header = request.headers.get("Authorization") or ""
    if not header.startswith("Bearer "):
        raise ApiError(401, "unauthenticated", "Present a bearer token.")

    token = header.removeprefix("Bearer ").strip()
    key_id, separator, secret = token.partition(".")
    if not separator or not key_id or not secret:
        raise ApiError(401, "malformed_token", "The token should be <key id>.<secret>.")

    client = ApiClient.objects.filter(key_id=key_id).first()
    # The secret is verified even when the client is missing, so a wrong key id
    # and a wrong secret take the same time to reject.
    if client is None:
        ApiClient(secret_hash="!").verify(secret)
        raise ApiError(401, "invalid_credentials", "The credentials were not accepted.")
    if not client.verify(secret):
        raise ApiError(401, "invalid_credentials", "The credentials were not accepted.")

    if not client.active:
        raise ApiError(403, "client_disabled", "This client has been disabled.")
    if client.is_expired:
        raise ApiError(403, "client_expired", "This client's credentials have expired.")

    allowed = client.allowed_ips or []
    if allowed:
        address = _client_ip(request)
        if address not in allowed:
            logger.warning("API client %s called from unlisted address %s", client.name, address)
            raise ApiError(403, "address_not_allowed", "This address is not on the client's allow-list.")

    return client


def enforce_rate_limit(client: ApiClient) -> None:
    """A fixed window per client per minute.

    Deliberately simple. The purpose is to stop a looping integration from
    exhausting the database, not to meter billing — a sliding-window counter
    would cost a round trip per request to solve a problem nobody has.

    **This is only a limit if the cache is shared between worker processes.**
    Django's default cache is per-process, so N gunicorn workers would allow N
    times the configured rate. ``apps.api.checks.rate_limiter_needs_a_shared_cache``
    raises a system check warning when that is the case in a non-debug
    deployment, because a limit that silently multiplies is worse than no
    limit at all.
    """
    limit = client.rate_limit_per_minute or 0
    if limit <= 0:
        return

    window = int(time.time() // 60)
    key = f"dx:api:rate:{client.pk}:{window}"
    try:
        count = cache.get_or_set(key, 0, timeout=120)
        count = cache.incr(key)
    except ValueError:
        # The key expired between get_or_set and incr.
        cache.set(key, 1, timeout=120)
        count = 1

    if count > limit:
        raise ApiError(
            429, "rate_limited",
            f"More than {limit} requests in a minute. Slow down and retry.",
            retry_after=60 - int(time.time() % 60),
        )


def require(*scopes: str, phi: bool = False):
    """Decorate a view as an API endpoint requiring these scopes.

    ``phi=True`` marks the endpoint as returning identifiable patient data, so
    the disclosure is recorded. Marking it is not optional bookkeeping — an
    unrecorded disclosure is the finding, not the disclosure itself.
    """

    def decorator(view):
        @csrf_exempt
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            from apps.audit.context import audit_as
            from apps.audit.models import AuditSource

            try:
                client = authenticate(request)
                enforce_rate_limit(client)

                missing = [scope for scope in scopes if not client.has_scope(scope)]
                if missing:
                    raise ApiError(
                        403, "insufficient_scope",
                        f"This client lacks the scope(s): {', '.join(missing)}.",
                        required=list(scopes),
                    )

                request.api_client = client
                with audit_as(
                    actor_username=f"api:{client.name}",
                    actor_role="api",
                    source=AuditSource.API,
                    ip_address=_client_ip(request),
                ):
                    response = view(request, *args, **kwargs)

                ApiClient.objects.filter(pk=client.pk).update(
                    last_used_at=timezone.now(),
                    request_count=models_f_increment(),
                )
                if phi:
                    _record_disclosure(request, client, response)
                return response

            except ApiError as error:
                return error.response()
            except Exception:
                logger.exception("Unhandled API error on %s", request.path)
                return ApiError(
                    500, "internal_error", "The request could not be completed."
                ).response()

        wrapper.api_scopes = scopes
        wrapper.api_returns_phi = phi
        return wrapper

    return decorator


def models_f_increment():
    from django.db.models import F

    return F("request_count") + 1


def _record_disclosure(request, client: ApiClient, response) -> None:
    """Log an API read of patient data for HIPAA accounting (§164.528).

    Only successful responses are recorded — a 404 discloses nothing, and
    recording it would make the accounting itself a way of probing for which
    patients exist.
    """
    if getattr(response, "status_code", 500) >= 300:
        return
    if not PHI_SCOPES.intersection(client.scopes or []):
        return

    from apps.compliance.models import PHIAccessLog

    try:
        PHIAccessLog.objects.create(
            username=f"api:{client.name}",
            patient_id=getattr(request, "api_patient_id", None),
            patient_mrn=getattr(request, "api_patient_mrn", "") or "",
            path=request.path[:512],
            method=request.method,
            purpose="operations",
            ip_address=_client_ip(request),
            justification=(
                f"API client {client.name}"
                + (f" for {client.organisation}" if client.organisation else "")
                + (f" — {client.purpose}" if client.purpose else "")
            ),
        )
    except Exception:
        logger.exception("Could not record API PHI access for %s", client.name)
