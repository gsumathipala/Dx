"""Audit trail browsing, entity history and chain integrity reporting."""
from __future__ import annotations

import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.models import AuditEvent, ChainCheckpoint, IntegrityAlert
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
    return user.is_authenticated and user.is_manager


def _filtered_events(request):
    """Apply the trail's filter form to the queryset."""
    events = AuditEvent.objects.all()

    query = (request.GET.get("q") or "").strip()
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

    context = {
        "page_obj": page,
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

    recomputed = hash_for_event(event)
    neighbours = AuditEvent.objects.filter(
        sequence__in=[event.sequence - 1, event.sequence + 1]
    ).order_by("sequence")

    return render(request, "audit/event_detail.html", {
        "event": event,
        "recomputed_hash": recomputed,
        "hash_valid": recomputed == event.hash,
        "neighbours": neighbours,
    })


@login_required
def entity_history(request, entity_type: str, entity_id: str):
    """Full change history for one record — the 'who touched this' view."""
    events = AuditEvent.objects.for_entity(entity_type, entity_id)
    paginator = Paginator(events, PAGE_SIZE)
    return render(request, "audit/entity_history.html", {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "page_obj": paginator.get_page(request.GET.get("page")),
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
    for event in events.iterator(chunk_size=1000):
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
