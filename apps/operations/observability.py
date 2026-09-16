"""Metrics, readiness and structured logging.

A clinical system that nobody is watching is a clinical system whose audit
recorder stopped three days ago. The existing ``/healthz`` answers "is the
process alive", which is the least interesting question — a process can be
alive while the audit chain has stopped being written, the webhook queue is
growing without bound and every instrument interface has gone silent.

Three things here:

* **/metrics** in Prometheus text exposition format. No dependency: the format
  is deliberately simple, and a client library would add a supply-chain
  surface for string formatting.
* **/readyz** for load balancers and orchestrators, distinct from liveness.
  Liveness asks "should you restart me"; readiness asks "should you send me
  traffic". Conflating them causes a restart loop under database pressure.
* **Structured JSON logging**, optional, so log lines are searchable in
  whatever the hospital already runs rather than being prose.

What is deliberately exposed and what is not
--------------------------------------------
Metrics carry **counts and states, never identifiers**. "Seventeen orders are
awaiting verification" is operational; "order 2026-09-16-0007 is awaiting
verification" is patient data, and a metrics endpoint is the one place in this
system nobody expects to find any.
"""
from __future__ import annotations

import json
import logging
import time

from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger("dx.observability")

#: Metrics are unauthenticated by default only when bound to a private
#: interface. Set METRICS_TOKEN to require a bearer token.
from django.conf import settings  # noqa: E402


def _metric(name: str, value, *, help_text: str, kind: str = "gauge",
            labels: dict | None = None) -> str:
    rendered_labels = ""
    if labels:
        pairs = ",".join(f'{k}="{_escape(str(v))}"' for k, v in sorted(labels.items()))
        rendered_labels = f"{{{pairs}}}"
    return (
        f"# HELP {name} {help_text}\n"
        f"# TYPE {name} {kind}\n"
        f"{name}{rendered_labels} {value}\n"
    )


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def collect() -> str:
    """Gather every metric. One pass, a handful of aggregate queries."""
    from django.db.models import Count

    from apps.api.models import WebhookDelivery
    from apps.audit.recorder import recorder
    from apps.clinical.models import CriticalValueNotification
    from apps.common.constants import OrderStatus
    from apps.interop.models import InstrumentInterface
    from apps.laboratory.models import Order
    from apps.operations.continuity import is_read_only
    from apps.operations.models import ExceptionItem

    out: list[str] = []

    # ── The audit trail: the thing whose silence matters most ────────────────
    out.append(_metric(
        "dx_audit_recorder_running", int(recorder.is_running()),
        help_text="1 when the audit recorder thread is alive. An audit trail "
                  "that stopped being written is the single worst silent failure.",
    ))
    out.append(_metric(
        "dx_audit_queue_depth", recorder.pending(),
        help_text="Audit events queued but not yet written. Sustained growth "
                  "means the database is not keeping up.",
    ))

    from apps.audit.models import AuditEvent

    out.append(_metric(
        "dx_audit_events_total", AuditEvent.objects.count(),
        help_text="Total audit events recorded.", kind="counter",
    ))

    # ── Work in progress ─────────────────────────────────────────────────────
    counts = dict(
        Order.objects.values_list("status").annotate(total=Count("id"))
    )
    for status, _label in OrderStatus.choices:
        out.append(_metric(
            "dx_orders", counts.get(status, 0),
            help_text="Orders by status.", labels={"status": status},
        ))

    # ── Things needing a person ──────────────────────────────────────────────
    by_severity = dict(
        ExceptionItem.objects.open().values_list("severity").annotate(total=Count("id"))
    )
    for severity in ("low", "medium", "high", "critical"):
        out.append(_metric(
            "dx_exceptions_open", by_severity.get(severity, 0),
            help_text="Open exception queue items by severity.",
            labels={"severity": severity},
        ))
    out.append(_metric(
        "dx_critical_values_pending",
        CriticalValueNotification.objects.filter(
            status=CriticalValueNotification.Status.PENDING
        ).count(),
        help_text="Critical values raised but not yet acknowledged.",
    ))

    # ── Interfaces and integrations ──────────────────────────────────────────
    interfaces = list(InstrumentInterface.objects.filter(enabled=True))
    out.append(_metric(
        "dx_interfaces_enabled", len(interfaces),
        help_text="Enabled instrument interfaces.",
    ))
    out.append(_metric(
        "dx_interfaces_stale", sum(1 for i in interfaces if i.is_stale),
        help_text="Enabled interfaces that have sent nothing for over an hour.",
    ))
    out.append(_metric(
        "dx_webhook_deliveries_pending",
        WebhookDelivery.objects.filter(status__in=[
            WebhookDelivery.Status.PENDING, WebhookDelivery.Status.RETRYING
        ]).count(),
        help_text="Webhook deliveries waiting. Growth means the deliverer is not running.",
    ))
    out.append(_metric(
        "dx_webhook_deliveries_failed",
        WebhookDelivery.objects.filter(status=WebhookDelivery.Status.FAILED).count(),
        help_text="Webhook deliveries that gave up.", kind="counter",
    ))

    # ── Mode ─────────────────────────────────────────────────────────────────
    out.append(_metric(
        "dx_read_only_mode", int(is_read_only()),
        help_text="1 when the system is refusing writes.",
    ))

    from apps.operations.models import DowntimeEvent, DowntimePack

    out.append(_metric(
        "dx_downtime_open", DowntimeEvent.objects.open().count(),
        help_text="Downtime events declared and not yet ended.",
    ))
    out.append(_metric(
        "dx_downtime_unreconciled",
        DowntimeEvent.objects.filter(
            ended_at__isnull=False, reconciled_at__isnull=True
        ).count(),
        help_text="Past outages whose paper results have not been confirmed entered.",
    ))

    latest_pack = DowntimePack.objects.first()
    out.append(_metric(
        "dx_downtime_pack_age_seconds",
        int(latest_pack.age_hours * 3600) if latest_pack else -1,
        help_text="Age of the newest downtime pack, or -1 if none exists. A "
                  "stale pack is a trap, not a safety net.",
    ))

    return "".join(out)


@csrf_exempt
def metrics(request):
    """Prometheus text exposition."""
    expected = getattr(settings, "METRICS_TOKEN", "")
    if expected:
        import hmac as _hmac

        presented = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        if not _hmac.compare_digest(presented, expected):
            return HttpResponse("Unauthorized\n", status=401, content_type="text/plain")

    started = time.monotonic()
    try:
        body = collect()
    except Exception:
        logger.exception("Metric collection failed")
        return HttpResponse(
            "# metric collection failed\n", status=500, content_type="text/plain"
        )

    body += _metric(
        "dx_metrics_collection_seconds", f"{time.monotonic() - started:.4f}",
        help_text="How long gathering these metrics took.",
    )
    return HttpResponse(body, content_type="text/plain; version=0.0.4; charset=utf-8")


@csrf_exempt
def readyz(request):
    """Readiness: should this instance be sent traffic?

    Distinct from liveness. Liveness asks "should you restart me"; a database
    that is briefly unreachable should take an instance *out of rotation*, not
    into a restart loop that makes the pressure worse.
    """
    checks: dict[str, bool] = {}
    detail: dict[str, str] = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = True
    except Exception as error:
        checks["database"] = False
        detail["database"] = str(error)[:200]

    try:
        from apps.audit.protection import is_installed

        checks["audit_immutability"] = bool(is_installed())
        if not checks["audit_immutability"]:
            detail["audit_immutability"] = (
                "The append-only triggers are not installed. The audit trail is "
                "not protected at the database level."
            )
    except Exception as error:
        checks["audit_immutability"] = False
        detail["audit_immutability"] = str(error)[:200]

    from apps.audit.recorder import recorder

    checks["audit_recorder"] = recorder.is_running()

    ready = all(checks.values())
    return JsonResponse(
        {
            "ready": ready,
            "checks": checks,
            "detail": detail,
            "checked_at": timezone.now().isoformat(),
        },
        status=200 if ready else 503,
    )


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for a log pipeline rather than a person.

    Enabled with ``DJANGO_LOG_FORMAT=json``. The request id is included where
    the audit context has one, so a log line can be tied to the audit events
    from the same request — which is the join an investigation actually needs.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": timezone.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        try:
            from apps.audit.context import get_context

            context = get_context()
            if context.request_id:
                payload["request_id"] = context.request_id
            if context.actor_username and context.actor_username != "system":
                payload["actor"] = context.actor_username
        except Exception:  # pragma: no cover - logging must never raise
            pass

        return json.dumps(payload, default=str)
