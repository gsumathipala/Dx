"""Audit trail browsing, entity history and chain integrity reporting."""
from __future__ import annotations

import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.models import AuditEvent, ChainCheckpoint, IntegrityAlert
from apps.audit.redaction import (
    REDACTED, apply as apply_redaction, is_phi_bearing, may_see_clinical_content,
    redact_event,
)
from apps.audit.recorder import recorder
from apps.audit.verification import (
    acknowledge_alert,
    latest_checkpoint,
    open_alerts,
    verify_and_checkpoint,
    verify_chain,
)
from apps.common.constants import AuditAction

PAGE_SIZE = 50


def _manager_required(user):
    """Managers assure the trail clinically; the installer assures it technically."""
    return user.is_authenticated and (user.is_manager or user.is_installer)


def _filtered_events(request):
    """Apply the trail's filter form to the queryset.

    For a user barred from patient data, clinical records are excluded from the
    free-text search entirely. Redacting the results would not be enough: a
    search for a medical record number that returned a hit would confirm the
    patient exists, which is itself a disclosure.
    """
    events = AuditEvent.objects.all()

    query = (request.GET.get("q") or "").strip()
    if query and not may_see_clinical_content(request.user):
        from apps.audit.redaction import PHI_BEARING_APPS, PHI_BEARING_MODELS

        for app_label in PHI_BEARING_APPS:
            events = events.exclude(entity_type__startswith=f"{app_label}.")
        events = events.exclude(entity_type__in=PHI_BEARING_MODELS)

    if query:
        events = events.filter(
            Q(entity_id__icontains=query)
            | Q(entity_label__icontains=query)
            | Q(actor_username__icontains=query)
            | Q(entity_type__icontains=query)
        )

    for field in ("entity_type", "action", "source"):
        value = request.GET.get(field)
        if value:
            events = events.filter(**{field: value})

    actor = request.GET.get("actor")
    if actor:
        events = events.filter(actor_username=actor)

    start, end = request.GET.get("from"), request.GET.get("to")
    if start:
        events = events.filter(timestamp__date__gte=start)
    if end:
        events = events.filter(timestamp__date__lte=end)

    return events


@login_required
def trail(request):
    """The main audit trail browser.

    Every user can see the trail — visibility of who changed what is part of
    the control, not an administrative privilege — but only managers can run
    verification or export.
    """
    events = _filtered_events(request).select_related()
    paginator = Paginator(events, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))
    visible = apply_redaction(page.object_list, request.user)

    context = {
        "page_obj": page,
        "events": visible,
        "redacting": not may_see_clinical_content(request.user),
        "total": paginator.count,
        "entity_types": AuditEvent.objects.values_list("entity_type", flat=True).distinct().order_by("entity_type"),
        "actors": AuditEvent.objects.values_list("actor_username", flat=True).distinct().order_by("actor_username"),
        "actions": AuditAction.choices,
        "filters": request.GET,
        "recorder_running": recorder.is_running(),
        "queue_depth": recorder.pending(),
    }
    return render(request, "audit/trail.html", context)


@login_required
def event_detail(request, sequence: int):
    event = get_object_or_404(AuditEvent, sequence=sequence)
    from apps.audit.hashing import hash_for_event

    # Verification runs against the stored event, never the redacted view —
    # otherwise redaction would look like tampering.
    recomputed = hash_for_event(event)
    hash_valid = recomputed == event.hash

    redacting = not may_see_clinical_content(request.user) and is_phi_bearing(event.entity_type)
    if redacting:
        event = redact_event(event)

    neighbours = AuditEvent.objects.filter(
        sequence__in=[event.sequence - 1, event.sequence + 1]
    ).order_by("sequence")

    return render(request, "audit/event_detail.html", {
        "event": event,
        "recomputed_hash": recomputed if not redacting else REDACTED,
        "hash_valid": hash_valid,
        "neighbours": neighbours,
        "redacting": redacting,
    })


@login_required
def entity_history(request, entity_type: str, entity_id: str):
    """Full change history for one record — the 'who touched this' view."""
    if is_phi_bearing(entity_type) and not may_see_clinical_content(request.user):
        # Redacting would not help: asking for one record's history and being
        # shown anything at all confirms the record exists.
        raise PermissionDenied(
            "This record's history concerns patient data, which your role may "
            "not see. The audit trail itself remains available to you, with "
            "clinical content redacted."
        )

    events = AuditEvent.objects.for_entity(entity_type, entity_id)
    paginator = Paginator(events, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "audit/entity_history.html", {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "page_obj": page,
        "events": list(page.object_list),
        "total": paginator.count,
        "latest_label": events.values_list("entity_label", flat=True).first() or entity_id,
    })


@login_required
@user_passes_test(_manager_required)
def integrity(request):
    """Chain integrity status, checkpoint history and open alerts."""
    window_start = timezone.now() - timedelta(days=30)
    activity = (
        AuditEvent.objects.filter(timestamp__gte=window_start)
        .values("action")
        .annotate(count=Count("sequence"))
        .order_by("-count")
    )

    return render(request, "audit/integrity.html", {
        "head": AuditEvent.objects.order_by("-sequence").first(),
        "event_count": AuditEvent.objects.count(),
        "checkpoint": latest_checkpoint(),
        "checkpoints": ChainCheckpoint.objects.all()[:20],
        "alerts": open_alerts(),
        "recorder_running": recorder.is_running(),
        "queue_depth": recorder.pending(),
        "activity": activity,
    })


@login_required
@user_passes_test(_manager_required)
@require_POST
def run_verification(request):
    """Verify the whole chain now and record a checkpoint."""
    result = verify_and_checkpoint()
    if result.ok:
        messages.success(request, result.summary)
    else:
        messages.error(request, result.summary)
    return redirect("audit:integrity")


@login_required
@user_passes_test(_manager_required)
@require_POST
def acknowledge(request, alert_id: int):
    acknowledge_alert(alert_id, request.user.username)
    messages.info(request, "Integrity alert acknowledged. The underlying discrepancy is not cleared.")
    return redirect("audit:integrity")


@login_required
@user_passes_test(_manager_required)
def export_csv(request):
    """Export the filtered trail for an inspector or an external archive."""
    events = _filtered_events(request)[:100_000]

    response = HttpResponse(content_type="text/csv")
    stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    response["Content-Disposition"] = f'attachment; filename="dx-audit-trail-{stamp}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "sequence", "timestamp", "actor", "role", "action", "entity_type",
        "entity_id", "entity_label", "changes", "reason", "source",
        "ip_address", "request_id", "previous_hash", "hash",
    ])
    redacting = not may_see_clinical_content(request.user)
    for event in events.iterator(chunk_size=1000):
        if redacting and is_phi_bearing(event.entity_type):
            event = redact_event(event)
        writer.writerow([
            event.sequence, event.timestamp.isoformat(), event.actor_username,
            event.actor_role or "", event.action, event.entity_type, event.entity_id,
            event.entity_label, event.changes, event.reason or "", event.source,
            event.ip_address or "", event.request_id or "", event.previous_hash, event.hash,
        ])

    from apps.audit.recorder import record

    record(
        action=AuditAction.RELEASE,
        entity_type="audit.AuditEvent",
        entity_id="export",
        entity_label=f"audit trail exported ({events.count()} rows)",
        changes={"filters": {"old": None, "new": dict(request.GET)}},
        blocking=True,
    )
    return response


@login_required
@user_passes_test(_manager_required)
def verify_api(request):
    """JSON verification endpoint for monitoring systems."""
    result = verify_chain()
    return JsonResponse({
        "ok": result.ok,
        "checked": result.checked,
        "head_sequence": result.head_sequence,
        "head_hash": result.head_hash,
        "problems": result.problems,
    }, status=200 if result.ok else 409)
