"""Emitting and delivering webhook events.

Emission is cheap and synchronous: a row per subscriber. Delivery is done by a
worker (``manage.py deliver_webhooks``), so a slow or hanging subscriber cannot
hold up the transaction that produced the event — a ward's HTTP endpoint must
never be able to stall result entry.

Payloads are signed::

    X-Dx-Signature: t=1736899200,v1=<hex HMAC-SHA256 of "t.body">

The receiver recomputes the HMAC with its shared secret and rejects anything
whose timestamp is more than five minutes old, which makes a captured payload
useless to replay. This is the same construction Stripe uses, for the same
reason: it is simple enough that people actually implement it correctly.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request

from django.db import transaction
from django.utils import timezone

from apps.api.models import Webhook, WebhookDelivery

logger = logging.getLogger("dx.api.webhooks")

USER_AGENT = "Dx-LIS-Webhook/1"
TIMEOUT_SECONDS = 10
#: Consecutive failures after which a subscriber is disabled outright.
DISABLE_AFTER = 20


def sign(secret: str, body: bytes, *, timestamp: int | None = None) -> str:
    timestamp = timestamp or int(time.time())
    signed = f"{timestamp}.".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify(secret: str, body: bytes, header: str, *, tolerance: int = 300) -> bool:
    """Reference implementation of the check a subscriber performs.

    Shipped here so the documentation can point at working code rather than
    prose, and so the tests exercise the same function a subscriber would.
    """
    parts = dict(
        piece.split("=", 1) for piece in (header or "").split(",") if "=" in piece
    )
    try:
        timestamp = int(parts.get("t", ""))
    except ValueError:
        return False
    if abs(time.time() - timestamp) > tolerance:
        return False
    expected = hmac.new(
        secret.encode("utf-8"), f"{timestamp}.".encode("utf-8") + body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, parts.get("v1", ""))


def emit(event: str, payload: dict) -> int:
    """Queue an event for every active subscriber. Returns how many.

    Called from inside the transaction that produced the event, but the
    delivery rows are written on commit — a rolled-back result must not
    generate a webhook saying it happened.
    """
    subscribers = [
        webhook for webhook in Webhook.objects.filter(active=True)
        if webhook.subscribes_to(event)
    ]
    if not subscribers:
        return 0

    def queue():
        for webhook in subscribers:
            body = dict(payload)
            if not webhook.include_identifiers:
                body = redact(body)
            WebhookDelivery.objects.create(webhook=webhook, event=event, payload=body)

    transaction.on_commit(queue)
    return len(subscribers)


IDENTIFIER_KEYS = frozenset({
    "mrn", "first_name", "last_name", "date_of_birth", "phone", "email",
    "address", "age", "gender", "patient_name",
})


def redact(payload: dict) -> dict:
    """Strip direct identifiers from an event payload.

    The surrogate patient id survives, so a subscriber that is entitled to the
    detail can fetch it over the API — where the read is authenticated, scoped
    and recorded as a disclosure. A webhook body, by contrast, lands in
    somebody's application log.
    """
    def walk(value):
        if isinstance(value, dict):
            return {
                key: ("[redacted]" if key in IDENTIFIER_KEYS else walk(item))
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [walk(item) for item in value]
        return value

    return walk(payload)


def deliver(delivery: WebhookDelivery) -> bool:
    """Attempt one delivery. Never raises."""
    webhook = delivery.webhook
    body = json.dumps({
        "id": str(delivery.pk),
        "event": delivery.event,
        "created_at": delivery.created_at.isoformat(),
        "data": delivery.payload,
    }).encode("utf-8")

    request = urllib.request.Request(
        webhook.url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-Dx-Event": delivery.event,
            "X-Dx-Delivery": str(delivery.pk),
            "X-Dx-Signature": sign(webhook.secret, body),
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            delivery.mark_delivered(response.status)
        if webhook.consecutive_failures:
            webhook.consecutive_failures = 0
            webhook.save(update_fields=["consecutive_failures"])
        return True

    except urllib.error.HTTPError as error:
        delivery.schedule_retry(
            error.read().decode("utf-8", errors="replace")[:500], error.code
        )
    except Exception as error:  # URLError, timeout, DNS, anything
        delivery.schedule_retry(str(error))

    webhook.consecutive_failures += 1
    fields = ["consecutive_failures"]
    if webhook.consecutive_failures >= DISABLE_AFTER and webhook.active:
        # A subscriber that has failed twenty times running is not coming back
        # on its own. Disabling it stops the queue growing without bound, and
        # the exception queue makes sure somebody is told.
        webhook.active = False
        webhook.disabled_reason = (
            f"Disabled automatically after {webhook.consecutive_failures} "
            f"consecutive delivery failures."
        )
        fields += ["active", "disabled_reason"]
    webhook.save(update_fields=fields)
    return False


def drain(limit: int = 200) -> dict[str, int]:
    """Deliver everything that is due. Returns a small summary."""
    due = (
        WebhookDelivery.objects
        .filter(status__in=[WebhookDelivery.Status.PENDING, WebhookDelivery.Status.RETRYING],
                next_attempt_at__lte=timezone.now())
        .select_related("webhook")
        .order_by("next_attempt_at")[:limit]
    )
    delivered = failed = 0
    for delivery in due:
        if deliver(delivery):
            delivered += 1
        else:
            failed += 1
    return {"delivered": delivered, "failed": failed}
