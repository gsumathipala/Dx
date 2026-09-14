"""Ambient request context for audit attribution.

Model signals fire deep inside the ORM where the HTTP request is not in scope.
A ``ContextVar`` carries the acting user and request metadata down to them, and
works correctly under threads and async views alike.
"""
from __future__ import annotations

import contextlib
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field, replace

from apps.audit.models import AuditSource


@dataclass(frozen=True)
class AuditContext:
    actor_id: str | None = None
    actor_username: str = "system"
    actor_role: str | None = None
    source: str = AuditSource.SYSTEM
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    session_key: str | None = None
    reason: str | None = None
    #: When False, signal-driven capture is suppressed (used by bulk imports
    #: that record their own summary event instead of one row per object).
    enabled: bool = True


_context: ContextVar[AuditContext] = ContextVar("dx_audit_context", default=AuditContext())


def get_context() -> AuditContext:
    return _context.get()


def set_context(ctx: AuditContext):
    return _context.set(ctx)


def reset_context(token) -> None:
    _context.reset(token)


def context_from_request(request) -> AuditContext:
    user = getattr(request, "user", None)
    authenticated = bool(user and getattr(user, "is_authenticated", False))
    path = request.path or ""
    source = AuditSource.API if path.startswith("/api/") else AuditSource.WEB
    return AuditContext(
        actor_id=str(user.pk) if authenticated else None,
        actor_username=user.username if authenticated else "anonymous",
        actor_role=getattr(user, "role", None) if authenticated else None,
        source=source,
        ip_address=client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:1000] or None,
        request_id=request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex,
        session_key=getattr(getattr(request, "session", None), "session_key", None),
    )


def client_ip(request) -> str | None:
    """Best-effort client address.

    Only the left-most X-Forwarded-For entry is used, and only when the deploy
    sits behind a trusted proxy; otherwise REMOTE_ADDR is authoritative.
    """
    from django.conf import settings

    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            candidate = forwarded.split(",")[0].strip()
            if candidate:
                return candidate
    return request.META.get("REMOTE_ADDR")


@contextlib.contextmanager
def audit_as(**overrides):
    """Temporarily override the ambient audit context.

    Used by management commands, the instrument interface and data migrations
    so their writes are attributed to something meaningful rather than 'system'.
    """
    token = _context.set(replace(_context.get(), **overrides))
    try:
        yield
    finally:
        _context.reset(token)


@contextlib.contextmanager
def suppress_auditing():
    """Disable automatic capture inside the block."""
    with audit_as(enabled=False):
        yield
