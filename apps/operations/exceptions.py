"""Raising, deduplicating and sweeping the exception queue.

Two ways items reach the queue:

**Pushed**, at the moment something goes wrong — a specimen is rejected, an
instrument message fails to parse, a rule asks for one. These call
:func:`raise_exception` directly from the code that noticed.

**Swept**, for conditions nobody is present to notice — a critical value that
has sat unacknowledged past its escalation deadline, an interface that has gone
quiet, a turnaround target already breached. :func:`sweep` looks for these and
is run from ``manage.py sweep_exceptions`` on a timer.

The distinction matters: a pushed item is an event, a swept item is a state.
Sweeping is idempotent because ``source_key`` deduplicates, so running it every
minute costs one pass and never produces a duplicate row.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.operations.models import ExceptionItem, ExceptionSource

logger = logging.getLogger("dx.exceptions")

__all__ = ["ExceptionSource", "raise_exception", "resolve", "acknowledge", "sweep"]


def raise_exception(
    *,
    source: str,
    source_key: str,
    title: str,
    detail: str = "",
    severity: str = ExceptionItem.Severity.MEDIUM,
    order=None,
    patient=None,
    test_code: str = "",
    entity_type: str = "",
    entity_id: str = "",
    due_at=None,
) -> ExceptionItem:
    """Put an item on the queue, or bump the one that is already there.

    Re-raising an item that a person already resolved *reopens* it — the
    problem came back, and closing it once does not mean it stays closed.
    Occurrences accumulate across the whole life of the item so a recurring
    fault is visible as one item with a high count rather than as noise.
    """
    now = timezone.now()
    patient_id = patient.pk if patient is not None else (
        order.patient_id if order is not None else None
    )

    with transaction.atomic():
        item, created = ExceptionItem.objects.get_or_create(
            source_key=source_key,
            defaults={
                "source": source,
                "title": title[:255],
                "detail": detail,
                "severity": severity,
                "order": order,
                "patient_id": patient_id,
                "test_code": test_code,
                "entity_type": entity_type,
                "entity_id": str(entity_id or ""),
                "due_at": due_at,
            },
        )
        if created:
            _announce(item)
            return item

        item.occurrences += 1
        item.last_seen_at = now
        fields = ["occurrences", "last_seen_at"]

        if not item.is_open:
            # It came back. Reopen rather than leaving a resolved row that no
            # longer describes reality.
            item.status = ExceptionItem.Status.OPEN
            item.raised_at = now
            item.resolved_at = None
            item.resolved_by = None
            item.resolution = ""
            fields += ["status", "raised_at", "resolved_at", "resolved_by", "resolution"]

        item.save(update_fields=fields)
        return item


def _announce(item: ExceptionItem) -> None:
    """Tell webhook subscribers a new item was raised."""
    try:
        from apps.api.webhooks import emit

        emit("exception.raised", {
            "exception_id": str(item.pk),
            "source": item.source,
            "title": item.title,
            "severity": item.severity,
            "accession_number": item.accession,
            "test_code": item.test_code,
            "raised_at": item.raised_at.isoformat(),
        })
    except Exception:
        logger.exception("Could not emit exception.raised for %s", item.pk)


def acknowledge(item: ExceptionItem, user) -> ExceptionItem:
    """Someone has taken ownership; the clock keeps running."""
    item.status = ExceptionItem.Status.ACKNOWLEDGED
    item.acknowledged_by = user
    item.acknowledged_at = timezone.now()
    if item.assigned_to_id is None:
        item.assigned_to = user
    item.save(update_fields=[
        "status", "acknowledged_by", "acknowledged_at", "assigned_to",
    ])
    return item


def resolve(item: ExceptionItem, user, *, resolution: str, dismissed: bool = False,
            raise_capa: bool = False) -> ExceptionItem:
    """Close an item, with a reason.

    A reason is mandatory. "Resolved" on its own tells the next inspector, and
    the next person to meet the same fault, nothing at all.
    """
    from apps.compliance.services import ControlViolation

    if not (resolution or "").strip():
        raise ControlViolation("A resolution note is required to close an exception.")

    item.status = (
        ExceptionItem.Status.DISMISSED if dismissed else ExceptionItem.Status.RESOLVED
    )
    item.resolved_by = user
    item.resolved_at = timezone.now()
    item.resolution = resolution.strip()
    fields = ["status", "resolved_by", "resolved_at", "resolution"]

    if raise_capa and item.corrective_action_id is None:
        from apps.compliance.models import CorrectiveAction
        from apps.compliance.services import raise_capa as open_capa

        item.corrective_action = open_capa(
            title=f"Exception: {item.title}"[:255],
            category=CorrectiveAction.Category.OTHER,
            description=f"{item.detail}\n\nResolution recorded: {resolution.strip()}",
            raised_by=user,
            severity=(
                CorrectiveAction.Severity.HIGH
                if item.severity in (ExceptionItem.Severity.HIGH, ExceptionItem.Severity.CRITICAL)
                else CorrectiveAction.Severity.MEDIUM
            ),
            linked_entity_type="operations.ExceptionItem",
            linked_entity_id=item.pk,
        )
        fields.append("corrective_action")

    item.save(update_fields=fields)
    return item


def auto_resolve(source_key: str, note: str) -> None:
    """Close an item because the underlying condition genuinely cleared.

    Used when the system can tell — a critical value gets acknowledged, an
    interface starts talking again. Recorded as a resolution with no user,
    which reads correctly in the queue's history.
    """
    item = ExceptionItem.objects.filter(source_key=source_key).first()
    if item is None or not item.is_open:
        return
    item.status = ExceptionItem.Status.RESOLVED
    item.resolved_at = timezone.now()
    item.resolution = note
    item.save(update_fields=["status", "resolved_at", "resolution"])


# ── Sweeping for conditions nobody reported ──────────────────────────────────


def _sweep_critical_values() -> int:
    from apps.clinical.models import CriticalValueNotification

    raised = 0
    overdue = (
        CriticalValueNotification.objects
        .filter(status=CriticalValueNotification.Status.PENDING,
                escalation_due_at__lt=timezone.now())
        .select_related("order", "test", "patient")
    )
    for notification in overdue:
        raise_exception(
            source=ExceptionSource.CRITICAL_VALUE,
            source_key=f"critical:{notification.pk}",
            title=f"Critical {notification.test_code} not acknowledged",
            detail=(
                f"{notification.test_code} = {notification.value} "
                f"({notification.threshold}) on {notification.order.accession_number} "
                f"passed its escalation deadline without documented read-back."
            ),
            severity=ExceptionItem.Severity.CRITICAL,
            order=notification.order,
            test_code=notification.test_code,
            entity_type="clinical.CriticalValueNotification",
            entity_id=notification.pk,
            due_at=notification.escalation_due_at,
        )
        raised += 1

    # Anything since acknowledged closes itself.
    for notification in CriticalValueNotification.objects.exclude(
        status=CriticalValueNotification.Status.PENDING
    ).values_list("pk", flat=True):
        auto_resolve(f"critical:{notification}", "The critical value was acknowledged.")

    return raised


def _sweep_tat_breaches() -> int:
    from apps.operations.models import TatBreach

    raised = 0
    recent = TatBreach.objects.filter(
        breach_type=TatBreach.BreachType.CRITICAL,
        resolved_at__isnull=True,
        detected_at__gte=timezone.now() - timedelta(days=7),
    ).select_related("order")
    for breach in recent:
        raise_exception(
            source=ExceptionSource.TAT_BREACH,
            source_key=f"tat:{breach.pk}",
            title=f"Turnaround breached on {breach.order.accession_number}",
            detail=(
                f"{breach.actual_hours:.1f} hours elapsed against a "
                f"{breach.target_hours:.1f} hour target."
            ),
            severity=ExceptionItem.Severity.MEDIUM,
            order=breach.order,
            entity_type="operations.TatBreach",
            entity_id=breach.pk,
        )
        raised += 1
    return raised


def _sweep_interfaces() -> int:
    from apps.interop.models import InstrumentInterface

    raised = 0
    for interface in InstrumentInterface.objects.filter(enabled=True):
        key = f"interface:{interface.pk}"
        if interface.is_stale:
            last = (
                f"last message {interface.last_message_at:%Y-%m-%d %H:%M}"
                if interface.last_message_at else "no message has ever been received"
            )
            raise_exception(
                source=ExceptionSource.INTERFACE_STALE,
                source_key=key,
                title=f"Interface {interface.name} is silent",
                detail=(
                    f"{interface.name} is enabled but has sent nothing for over an hour "
                    f"({last}). Results may be accumulating on the analyser."
                ),
                severity=ExceptionItem.Severity.HIGH,
                entity_type="interop.InstrumentInterface",
                entity_id=interface.pk,
            )
            raised += 1
        else:
            auto_resolve(key, "The interface is sending again.")
    return raised


def _sweep_instrument_failures() -> int:
    from apps.interop.models import InstrumentMessage

    raised = 0
    failures = InstrumentMessage.objects.filter(
        status=InstrumentMessage.Status.FAILED,
        received_at__gte=timezone.now() - timedelta(days=3),
    ).select_related("interface")
    for message in failures:
        raise_exception(
            source=ExceptionSource.INSTRUMENT,
            source_key=f"instrument-message:{message.pk}",
            title=f"Instrument message failed on {message.interface.name if message.interface_id else 'an unknown interface'}",
            detail=message.error or "The message could not be applied to an order.",
            severity=ExceptionItem.Severity.HIGH,
            entity_type="interop.InstrumentMessage",
            entity_id=message.pk,
        )
        raised += 1
    return raised


def _sweep_qc_failures() -> int:
    from apps.quality.models import QcRun

    raised = 0
    failures = QcRun.objects.filter(
        status=QcRun.Status.FAIL,
        timestamp__gte=timezone.now() - timedelta(days=2),
    ).select_related("definition", "definition__material")
    for run in failures:
        code = run.definition.test_code if run.definition_id else "?"
        material = run.definition.material.name if run.definition_id else ""
        raise_exception(
            source=ExceptionSource.QC_FAILURE,
            source_key=f"qc:{run.pk}",
            title=f"QC failed for {code}",
            detail=(
                f"Control {material} gave {run.value} — "
                f"{', '.join(run.result_flags or []) or 'out of range'}. "
                "Patient results for this analyte are blocked until QC is acceptable."
            ),
            severity=ExceptionItem.Severity.CRITICAL,
            test_code=code,
            entity_type="quality.QcRun",
            entity_id=run.pk,
        )
        raised += 1
    return raised


def _sweep_webhooks() -> int:
    from apps.api.models import WebhookDelivery

    raised = 0
    failing = (
        WebhookDelivery.objects
        .filter(status=WebhookDelivery.Status.FAILED)
        .select_related("webhook")
    )
    seen: set[str] = set()
    for delivery in failing:
        if delivery.webhook_id in seen:
            continue
        seen.add(delivery.webhook_id)
        raise_exception(
            source=ExceptionSource.WEBHOOK,
            source_key=f"webhook:{delivery.webhook_id}",
            title=f"Webhook {delivery.webhook.name} is failing",
            detail=(
                f"Delivery to {delivery.webhook.url} gave up after "
                f"{delivery.attempts} attempts: {delivery.last_error or 'no response'}."
            ),
            severity=ExceptionItem.Severity.MEDIUM,
            entity_type="api.Webhook",
            entity_id=delivery.webhook_id,
        )
        raised += 1
    return raised


def _sweep_subject_requests() -> int:
    from apps.compliance.models import DataSubjectRequest

    raised = 0
    due = DataSubjectRequest.objects.open().filter(due_at__lt=timezone.now())
    for request in due:
        raise_exception(
            source=ExceptionSource.SUBJECT_REQUEST,
            source_key=f"subject-request:{request.pk}",
            title=f"Data subject request overdue ({request.get_kind_display()})",
            detail=(
                "A data subject request has passed its statutory response "
                "deadline. GDPR Article 12(3) allows one month, extendable by "
                "two months where the request is complex — but the extension "
                "must be communicated to the subject within the first month."
            ),
            severity=ExceptionItem.Severity.HIGH,
            entity_type="compliance.DataSubjectRequest",
            entity_id=request.pk,
            due_at=request.due_at,
        )
        raised += 1
    return raised


SWEEPS = (
    ("critical values", _sweep_critical_values),
    ("turnaround breaches", _sweep_tat_breaches),
    ("instrument interfaces", _sweep_interfaces),
    ("instrument messages", _sweep_instrument_failures),
    ("quality control", _sweep_qc_failures),
    ("webhook deliveries", _sweep_webhooks),
    ("data subject requests", _sweep_subject_requests),
)


def sweep() -> dict[str, int]:
    """Run every sweep. One failing sweep must not stop the others."""
    counts: dict[str, int] = {}
    for label, function in SWEEPS:
        try:
            counts[label] = function()
        except Exception:
            logger.exception("Exception sweep %r failed", label)
            counts[label] = -1
    return counts
