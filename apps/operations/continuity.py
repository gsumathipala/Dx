"""Business continuity: downtime packs, read-only mode and backloading.

What a laboratory does when the LIS is down
-------------------------------------------
It does not stop. Blood keeps arriving and clinicians keep needing answers, so
the laboratory runs on paper — and every accreditation body asks to see the
procedure for exactly that, in writing, tested.

Three things have to work:

1. **Knowing what was already requested.** A downtime pack, generated on a
   timer and readable with no server, no database and no network, because
   those are the things that are missing when it is needed. It is a plain HTML
   file: outstanding orders, who they belong to, what was asked for, and each
   patient's recent verified results so somebody can answer "what was their
   last potassium" without the system.

2. **Producing results safely meanwhile.** Printed worksheets from the same
   pack, carrying the reference and critical limits, so a result written by
   hand is still checked against something.

3. **Getting them back in afterwards.** Backloading records *two* people: the
   person who actually performed the test, and the person keying it in days
   later. CLIA §493.1291 wants the report to name the person who performed
   the examination; recording the typist would be false attribution, and it
   is the attribution an inspector checks first.

Read-only mode
--------------
Separate from downtime, and used during recovery: the system is up, reachable,
and must not be written to until the database is known-good. Refusing writes
loudly is far better than a restore racing against live traffic.
"""
from __future__ import annotations

import html
import logging
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.constants import AuditAction, OrderStatus

logger = logging.getLogger("dx.continuity")

#: The key in SystemSetting that puts the application into read-only mode.
READ_ONLY_KEY = "read_only_mode"

#: Statuses whose orders belong in a downtime pack — work the laboratory still
#: owes somebody an answer for.
OUTSTANDING = (
    OrderStatus.PENDING, OrderStatus.IN_PROGRESS, OrderStatus.RECEIVED,
    OrderStatus.RESULTED, OrderStatus.TECHNICALLY_VALIDATED,
)


# ── Read-only mode ───────────────────────────────────────────────────────────


def read_only_reason() -> str | None:
    """The reason the system is read-only, or None when it is writable."""
    from apps.operations.models import SystemSetting

    setting = SystemSetting.objects.filter(key=READ_ONLY_KEY).first()
    if setting is None or not setting.value:
        return None
    return str(setting.value)


def is_read_only() -> bool:
    return read_only_reason() is not None


def set_read_only(reason: str | None, *, user=None) -> None:
    """Enter or leave read-only mode. Always audited — it stops clinical work."""
    from apps.audit.recorder import record
    from apps.operations.models import SystemSetting

    previous = read_only_reason()
    SystemSetting.objects.update_or_create(
        key=READ_ONLY_KEY,
        defaults={
            "value": (reason or "").strip(),
            "description": "Set by the maintenance screen; refuses writes across the application.",
        },
    )

    record(
        action=AuditAction.UPDATE,
        entity_type="operations.SystemSetting",
        entity_id=READ_ONLY_KEY,
        entity_label=(
            f"system placed in read-only mode: {reason}" if reason
            else "read-only mode lifted"
        ),
        changes={"read_only_mode": {"old": previous, "new": reason or None}},
        reason=reason or "Read-only mode lifted.",
        blocking=True,
    )


# ── Downtime events ──────────────────────────────────────────────────────────


def next_reference() -> str:
    from apps.operations.models import DowntimeEvent

    year = timezone.now().year
    prefix = f"DT-{year}-"
    highest = 0
    for reference in DowntimeEvent.objects.filter(
        reference__startswith=prefix
    ).values_list("reference", flat=True):
        suffix = reference.rsplit("-", 1)[-1]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:04d}"


@transaction.atomic
def declare(*, kind: str, reason: str, user=None, began_at=None, expected_end=None,
            impact: str = ""):
    """Open a downtime record.

    Called when the laboratory notices, which for an unplanned outage is after
    it started — hence ``began_at``, which should be when the system was
    actually lost rather than when somebody got round to logging it. Turnaround
    figures and the reconciliation window both depend on the real time.
    """
    from apps.audit.recorder import record
    from apps.operations.models import DowntimeEvent

    event = DowntimeEvent.objects.create(
        reference=next_reference(),
        kind=kind,
        began_at=began_at or timezone.now(),
        declared_by=user,
        expected_end=expected_end,
        reason=reason,
        impact=impact,
    )
    record(
        action=AuditAction.CREATE,
        entity_type="operations.DowntimeEvent",
        entity_id=event.pk,
        entity_label=f"{event.reference}: {event.get_kind_display()} downtime declared",
        reason=reason,
        blocking=True,
    )
    return event


@transaction.atomic
def end(event, *, user, recovery_notes: str = ""):
    """Mark the system back. This does *not* close the event.

    An outage is closed when everything produced on paper is in the record,
    not when the server comes back. Keeping the two separate is what stops a
    handful of handwritten results being quietly forgotten.
    """
    from apps.audit.recorder import record

    event.ended_at = timezone.now()
    event.ended_by = user
    event.recovery_notes = recovery_notes
    event.save(update_fields=["ended_at", "ended_by", "recovery_notes"])

    record(
        action=AuditAction.UPDATE,
        entity_type="operations.DowntimeEvent",
        entity_id=event.pk,
        entity_label=f"{event.reference}: system restored after {event.duration_hours:.1f}h",
        reason=recovery_notes or "System restored.",
        blocking=True,
    )

    from apps.operations.exceptions import ExceptionSource, raise_exception

    raise_exception(
        source=ExceptionSource.MANUAL,
        source_key=f"downtime-reconcile:{event.pk}",
        title=f"Reconcile downtime {event.reference}",
        detail=(
            f"The system was down for {event.duration_hours:.1f} hours. Every "
            "result produced on paper must be entered before this is closed."
        ),
        severity="high",
        entity_type="operations.DowntimeEvent",
        entity_id=event.pk,
    )
    return event


@transaction.atomic
def reconcile(event, *, user, notes: str = ""):
    """Confirm every paper result is in. Requires the event to have ended."""
    from apps.audit.recorder import record
    from apps.compliance.services import ControlViolation
    from apps.operations.exceptions import auto_resolve

    if event.ended_at is None:
        raise ControlViolation(
            "The system is still down. End the downtime before reconciling it."
        )

    event.reconciled_at = timezone.now()
    event.reconciled_by = user
    if notes:
        event.recovery_notes = f"{event.recovery_notes}\n{notes}".strip()
    event.save(update_fields=["reconciled_at", "reconciled_by", "recovery_notes"])

    auto_resolve(
        f"downtime-reconcile:{event.pk}",
        f"Reconciled by {user.username}: {event.backloaded_results} result(s) backloaded.",
    )
    record(
        action=AuditAction.UPDATE,
        entity_type="operations.DowntimeEvent",
        entity_id=event.pk,
        entity_label=(
            f"{event.reference}: reconciled — {event.backloaded_results} "
            "result(s) entered from paper"
        ),
        reason=notes or "Downtime reconciled.",
        blocking=True,
    )
    return event


# ── Backloading ──────────────────────────────────────────────────────────────


@transaction.atomic
def backload(*, order, values: dict, event, performed_by: str, performed_at,
             keyed_by, reason: str = ""):
    """Enter results that were produced on paper during an outage.

    Two people are recorded. ``performed_by`` is whoever actually ran the test
    and wrote the number down; ``keyed_by`` is whoever typed it in afterwards.
    CLIA §493.1291(c) requires the report to identify the person performing the
    examination, and after an outage those are rarely the same person.

    The result carries the time it was *produced*, not the time it was typed,
    so turnaround figures describe what happened to the patient rather than
    what happened to the keyboard.
    """
    from apps.audit.context import audit_as
    from apps.audit.recorder import record
    from apps.compliance.services import ControlViolation
    from apps.laboratory.models import Result, TestDefinition

    if not performed_by.strip():
        raise ControlViolation(
            "Name the person who performed the test. The person typing it in "
            "afterwards is not the person the report must identify.",
            "CLIA 42 CFR §493.1291(c)",
        )
    if performed_at is None:
        raise ControlViolation("Record when the result was actually produced.")
    if performed_at > timezone.now():
        raise ControlViolation("A result cannot have been produced in the future.")

    tests = {t.id: t for t in TestDefinition.objects.filter(id__in=values.keys())}
    written = []

    note = (
        f"Entered from paper after downtime {event.reference}. "
        f"Performed by {performed_by} at {performed_at:%Y-%m-%d %H:%M}, "
        f"entered by {keyed_by.username}."
    )

    with audit_as(reason=note):
        for test_id, raw in values.items():
            test = tests.get(test_id)
            if test is None:
                raise ControlViolation(f"Unknown test {test_id}.")

            result, _created = Result.objects.update_or_create(
                order=order, test_key=test_id,
                defaults={
                    "test": test,
                    "value": str(raw),
                    "status": OrderStatus.RESULTED,
                    "entered_by": performed_by,
                    "timestamp": performed_at,
                },
            )
            result.recompute_flags()
            existing_comment = result.comments or ""
            if note not in existing_comment:
                result.comments = f"{existing_comment}\n{note}".strip()
            result.save(update_fields=["result_flags", "comments"])
            written.append(result)

        order.status = OrderStatus.RESULTED
        order.updated_at = timezone.now()
        order.save(update_fields=["status", "updated_at"])

    event.backloaded_results = event.backloaded_results + len(written)
    event.save(update_fields=["backloaded_results"])

    record(
        action=AuditAction.CREATE,
        entity_type="laboratory.Order",
        entity_id=order.pk,
        entity_label=(
            f"{len(written)} result(s) backloaded from downtime {event.reference}"
        ),
        changes={"backloaded": {"old": None, "new": sorted(values.keys())}},
        reason=reason or note,
        blocking=True,
    )
    return written


# ── The downtime pack ────────────────────────────────────────────────────────


def _escape(value) -> str:
    return html.escape("" if value is None else str(value))


def build_pack(*, recent_hours: int = 72) -> tuple[str, dict]:
    """Render the downtime pack as a self-contained HTML document.

    No stylesheets, no scripts, no images, no network. It is opened from a USB
    stick on a machine that may have nothing else working, and it must print
    legibly on a ward printer.
    """
    from apps.clinical.models import CriticalValueNotification
    from apps.laboratory.models import Order, Result, TestDefinition
    from apps.reporting.models import Requester

    generated = timezone.now()
    since = generated - timedelta(hours=recent_hours)

    orders = list(
        Order.objects.filter(status__in=OUTSTANDING)
        .select_related("patient", "requester")
        .prefetch_related("tests", "results__test")
        .order_by("patient__last_name", "accession_number")
    )
    patients = {order.patient_id: order.patient for order in orders}

    recent = (
        Result.objects.filter(
            order__patient_id__in=patients.keys(),
            timestamp__gte=since,
            clinical_verified_by__isnull=False,
        )
        .select_related("test", "order")
        .order_by("order__patient_id", "test_key", "-timestamp")
    )
    recent_by_patient: dict[str, list] = {}
    for result in recent:
        recent_by_patient.setdefault(result.order.patient_id, []).append(result)

    pending_criticals = list(
        CriticalValueNotification.objects
        .filter(status=CriticalValueNotification.Status.PENDING)
        .select_related("patient", "order")[:100]
    )

    parts: list[str] = [f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Dx downtime pack — {generated:%Y-%m-%d %H:%M}</title>
<style>
 body {{ font: 12px/1.45 "DejaVu Sans", Arial, sans-serif; margin: 18px; color: #111; }}
 h1 {{ font-size: 18px; margin: 0 0 4px; }}
 h2 {{ font-size: 14px; margin: 22px 0 6px; border-bottom: 1px solid #999; }}
 table {{ border-collapse: collapse; width: 100%; margin-bottom: 14px; }}
 th, td {{ border: 1px solid #bbb; padding: 3px 5px; text-align: left;
          vertical-align: top; font-size: 11px; }}
 th {{ background: #eee; }}
 .warn {{ border: 2px solid #b00; padding: 8px; margin-bottom: 14px; }}
 .mono {{ font-family: "DejaVu Sans Mono", monospace; }}
 .crit {{ background: #ffe8e8; }}
 @media print {{ body {{ margin: 8mm; }} h2 {{ page-break-after: avoid; }} }}
</style></head><body>
<h1>Dx laboratory downtime pack</h1>
<p class="mono">Generated {generated:%A %d %B %Y at %H:%M %Z}</p>

<div class="warn">
<strong>This is a snapshot, not the system.</strong>
It was correct at the time above and has not changed since. Anything requested
or resulted after that time is not here. Results recorded on paper during the
outage must be entered against the downtime record once the system returns —
recording who performed the test and when, not who typed it in.
</div>
"""]

    # ── Outstanding work ─────────────────────────────────────────────────────
    parts.append(f"<h2>Outstanding orders ({len(orders)})</h2>")
    if not orders:
        parts.append("<p>No outstanding orders at the time of generation.</p>")
    else:
        parts.append(
            "<table><tr><th>Accession</th><th>Patient</th><th>MRN</th>"
            "<th>DOB</th><th>Sex</th><th>Priority</th><th>Status</th>"
            "<th>Requested</th><th>Tests</th><th>Requester</th></tr>"
        )
        for order in orders:
            patient = order.patient
            codes = ", ".join(sorted(test.code for test in order.tests.all()))
            parts.append(
                "<tr>"
                f"<td class='mono'>{_escape(order.accession_number)}</td>"
                f"<td>{_escape(patient.full_name)}</td>"
                f"<td class='mono'>{_escape(patient.mrn)}</td>"
                f"<td>{_escape(patient.dob)}</td>"
                f"<td>{_escape(patient.gender)}</td>"
                f"<td>{_escape(order.priority)}</td>"
                f"<td>{_escape(order.status)}</td>"
                f"<td>{order.timestamp:%d/%m %H:%M}</td>"
                f"<td>{_escape(codes)}</td>"
                f"<td>{_escape(order.order_by)}</td>"
                "</tr>"
            )
        parts.append("</table>")

    # ── Unacknowledged critical values ───────────────────────────────────────
    if pending_criticals:
        parts.append(f"<h2>Critical values not yet acknowledged ({len(pending_criticals)})</h2>")
        parts.append(
            "<table><tr><th>Accession</th><th>Patient</th><th>MRN</th>"
            "<th>Test</th><th>Value</th><th>Limit</th><th>Raised</th></tr>"
        )
        for item in pending_criticals:
            parts.append(
                "<tr class='crit'>"
                f"<td class='mono'>{_escape(item.order.accession_number)}</td>"
                f"<td>{_escape(item.patient.full_name)}</td>"
                f"<td class='mono'>{_escape(item.patient.mrn)}</td>"
                f"<td>{_escape(item.test_code)}</td>"
                f"<td><strong>{_escape(item.value)}</strong></td>"
                f"<td>{_escape(item.threshold)}</td>"
                f"<td>{item.created_at:%d/%m %H:%M}</td>"
                "</tr>"
            )
        parts.append("</table>")

    # ── Recent verified results, for comparison ──────────────────────────────
    parts.append(f"<h2>Recent verified results (last {recent_hours} hours)</h2>")
    parts.append(
        "<p>So a result written by hand can still be compared with the "
        "patient's own history.</p>"
    )
    if not recent_by_patient:
        parts.append("<p>None.</p>")
    for patient_id, results in recent_by_patient.items():
        patient = patients[patient_id]
        parts.append(
            f"<h3>{_escape(patient.full_name)} "
            f"<span class='mono'>({_escape(patient.mrn)})</span></h3>"
        )
        parts.append("<table><tr><th>Test</th><th>Value</th><th>Units</th>"
                     "<th>Flags</th><th>Reported</th></tr>")
        for result in results[:40]:
            parts.append(
                "<tr>"
                f"<td>{_escape(result.test.code if result.test_id else result.test_key)}</td>"
                f"<td><strong>{_escape(result.value)}</strong></td>"
                f"<td>{_escape(result.test.units if result.test_id else '')}</td>"
                f"<td>{_escape(', '.join(result.result_flags or []))}</td>"
                f"<td>{result.timestamp:%d/%m %H:%M}</td>"
                "</tr>"
            )
        parts.append("</table>")

    # ── Reference and critical limits ────────────────────────────────────────
    parts.append("<h2>Reference intervals and critical limits</h2>")
    parts.append(
        "<table><tr><th>Code</th><th>Test</th><th>Units</th>"
        "<th>Reference</th><th>Critical low</th><th>Critical high</th></tr>"
    )
    for test in TestDefinition.objects.filter(active=True).order_by("code"):
        parts.append(
            "<tr>"
            f"<td class='mono'>{_escape(test.code)}</td>"
            f"<td>{_escape(test.name)}</td>"
            f"<td>{_escape(test.units)}</td>"
            f"<td>{_escape(test.reference_display)}</td>"
            f"<td>{_escape(test.panic_low)}</td>"
            f"<td>{_escape(test.panic_high)}</td>"
            "</tr>"
        )
    parts.append("</table>")

    # ── Who to telephone ─────────────────────────────────────────────────────
    requesters = list(Requester.objects.filter(active=True).order_by("name")[:200])
    if requesters:
        parts.append("<h2>Requester contacts</h2>")
        parts.append("<table><tr><th>Name</th><th>Location</th><th>Telephone</th><th>Email</th></tr>")
        for requester in requesters:
            parts.append(
                "<tr>"
                f"<td>{_escape(requester.name)}</td>"
                f"<td>{_escape(getattr(requester, 'location', '') or getattr(requester, 'department', ''))}</td>"
                f"<td class='mono'>{_escape(getattr(requester, 'phone', ''))}</td>"
                f"<td>{_escape(getattr(requester, 'email', ''))}</td>"
                "</tr>"
            )
        parts.append("</table>")

    parts.append(
        "<h2>When the system returns</h2>"
        "<ol>"
        "<li>Do not start typing results in until somebody has confirmed the "
        "database is intact — the maintenance screen shows the audit chain "
        "verification.</li>"
        "<li>Open the downtime record and enter each paper result against it, "
        "naming <strong>who performed the test and when</strong>, not who is "
        "typing.</li>"
        "<li>Re-check every critical value listed above: some will have been "
        "telephoned during the outage and will need documenting.</li>"
        "<li>Reconcile the downtime record only when every paper result is in. "
        "Until then it stays on the exception queue.</li>"
        "</ol>"
        "</body></html>"
    )

    document = "".join(parts)
    stats = {
        "orders": len(orders),
        "patients": len(patients),
        "criticals": len(pending_criticals),
    }
    return document, stats


def write_pack(*, directory: Path | None = None, passphrase: str | None = None,
               generated_by: str = "", recent_hours: int = 72):
    """Write the pack to disk and record that it was written.

    **On encryption.** A downtime pack is concentrated patient data on a
    filesystem, and every other export this system produces is encrypted. This
    one is not, by default, and the reason is worth stating plainly: a pack you
    need our tooling to open is a pack you cannot open when our tooling is the
    thing that is down. The honest control is full-disk encryption on the
    machine that holds it, and physical control of that machine.

    Passing a passphrase encrypts it anyway, for sites whose policy requires
    that — with the consequence above accepted.
    """
    from apps.compliance.encryption import encrypt_bytes
    from apps.operations.models import DowntimePack

    document, stats = build_pack(recent_hours=recent_hours)
    body = document.encode("utf-8")

    directory = Path(directory or getattr(
        settings, "DOWNTIME_PACK_DIR", Path(settings.MEDIA_ROOT) / "downtime"
    ))
    directory.mkdir(parents=True, exist_ok=True)

    stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
    if passphrase:
        destination = directory / f"downtime-pack-{stamp}.html.dxenc"
        destination.write_bytes(encrypt_bytes(body, passphrase))
    else:
        destination = directory / f"downtime-pack-{stamp}.html"
        destination.write_bytes(body)

    # Also keep a stable filename, so the procedure can say "open
    # downtime-pack-latest.html" rather than "find the newest file".
    latest = directory / ("downtime-pack-latest.html.dxenc" if passphrase
                          else "downtime-pack-latest.html")
    latest.write_bytes(destination.read_bytes())

    pack = DowntimePack.objects.create(
        path=str(destination),
        encrypted=bool(passphrase),
        order_count=stats["orders"],
        patient_count=stats["patients"],
        bytes_written=len(body),
        generated_by=generated_by,
    )
    logger.info(
        "Downtime pack written to %s (%s order(s), %s patient(s), %s bytes)",
        destination, stats["orders"], stats["patients"], len(body),
    )
    return pack
