"""Deployment checks for the API.

Registered as Django system checks so they run on every ``manage.py check``,
every ``runserver`` and — importantly — in CI, rather than living in a
deployment document nobody reads.
"""
from __future__ import annotations

import os

from django.conf import settings
from django.core.checks import Warning, register

LOCAL_MEMORY_BACKENDS = {
    "django.core.cache.backends.locmem.LocMemCache",
    "django.core.cache.backends.dummy.DummyCache",
}


@register("dx")
def rate_limiter_needs_a_shared_cache(app_configs, **kwargs):
    """The API rate limit is only a limit if every worker counts the same way.

    Django's default cache is per-process. With N gunicorn workers and no
    shared cache, a client is allowed N times its configured rate, and a
    looping integration can exhaust the database despite the limit appearing
    to be set correctly. That is worse than having no limit, because the
    setting says otherwise.
    """
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if backend not in LOCAL_MEMORY_BACKENDS:
        return []
    if settings.DEBUG:
        return []

    return [
        Warning(
            "The API rate limiter is counting in a per-process cache.",
            hint=(
                "CACHES['default'] is "
                f"{backend.rsplit('.', 1)[-1]}, which is not shared between "
                "worker processes. Every gunicorn worker will allow the full "
                "rate_limit_per_minute, so a client gets N times its limit. "
                "Set DJANGO_CACHE_BACKEND and DJANGO_CACHE_LOCATION to a "
                "shared cache (Redis, Memcached, or "
                "django.core.cache.backends.db.DatabaseCache with "
                "`manage.py createcachetable`) before running more than one "
                "worker."
            ),
            id="dx.W001",
        )
    ]


@register("dx")
def audit_spool_must_be_durable(app_configs, **kwargs):
    """A spool on ephemeral storage loses the events it exists to protect."""
    if settings.DEBUG:
        return []

    spool = str(getattr(settings, "AUDIT_SPOOL_FILE", ""))
    if not spool.startswith(("/tmp/", "/var/tmp/")):
        return []

    return [
        Warning(
            "The audit spool is on temporary storage.",
            hint=(
                f"AUDIT_SPOOL_FILE is {spool}. Events that cannot reach the "
                "database are written there and replayed by `manage.py "
                "audit_worker`. On /tmp they are lost on reboot or container "
                "restart — which is exactly when they are most likely to "
                "exist. Point it at durable, backed-up storage."
            ),
            id="dx.W002",
        )
    ]
