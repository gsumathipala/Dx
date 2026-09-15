"""Dashboard, KPIs, messaging, storage, custody tracking and configuration."""
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from apps.common.constants import (
    LAB_STAFF_ROLES, MANAGEMENT_ROLES, SYSTEM_ROLES, OrderStatus, Role,
)
from apps.common.views import DxCreateView, DxListView, DxUpdateView
from apps.operations import forms as ops_forms
from apps.operations.models import (
    ChainOfCustodyEvent, Feedback, Message, RoutingAssignment, RoutingRule,
    StorageAssignment, StorageLocation, SystemAlert, SystemSetting, TatBreach,
    TatThreshold, Worksheet, Workstation,
)

LAB_STAFF = tuple(LAB_STAFF_ROLES)
MANAGERS = tuple(MANAGEMENT_ROLES)
ADMIN_ONLY = (Role.ADMIN,)
SYSTEM = tuple(SYSTEM_ROLES)
#: Screens both a manager and the installer need.
MANAGERS_AND_INSTALLER = tuple(dict.fromkeys(MANAGERS + SYSTEM))


def healthz(request):
    """Liveness probe — also reports whether the audit recorder is running."""
    from apps.audit.recorder import recorder

    return JsonResponse({
        "status": "ok",
        "audit_recorder": "running" if recorder.is_running() else "stopped",
        "audit_queue_depth": recorder.pending(),
    })


@login_required
def search(request):
    """Resolve an identifier from anywhere in the application.

    An exact accession number or MRN navigates straight to the record — the
    common case when someone has just scanned a tube. Anything else lists what
    matched.
    """
    from apps.operations.search import resolve_exact, search as run_search

    query = (request.GET.get("q") or "").strip()

    destination = resolve_exact(query)
    if destination:
        return redirect(destination)

    return render(request, "operations/search.html", {
        "query": query,
        "hits": run_search(query),
    })


@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.is_manager or u.is_installer))
def settings_index(request):
    """Searchable index of every configuration screen.

    These used to be 25 flat entries in the sidebar. Nobody scans a list that
    long for "Delta Check Rules" — they type "delta".
    """
    from apps.accounts.context_processors import settings_index as build_index

    query = (request.GET.get("q") or "").strip().lower()
    items = build_index(request.user)
    if query:
        items = [item for item in items if query in item.haystack]

    grouped: dict[str, list] = {}
    for item in items:
        grouped.setdefault(item.group, []).append(item)

    return render(request, "operations/settings_index.html", {
        "grouped": grouped,
        "query": request.GET.get("q", ""),
        "total": len(items),
    })


@login_required
def dashboard(request):
    """What needs this user now, not what happened yesterday.

    The previous version was seven stat tiles and four links — it reported
    rather than dispatched. Every row here is an action someone can take.
    """
    from apps.clinical.models import CriticalValueNotification
    from apps.inventory.services import low_stock_items
    from apps.laboratory.models import Order

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    orders = Order.objects.all()

    # ── The queues this person can actually clear ────────────────────────────
    queues = []
    if request.user.is_lab_staff:
        # One grouped query for all the queue sizes, rather than a COUNT each.
        sizes = {
            row["status"]: row["n"]
            for row in orders.values("status").annotate(n=Count("id"))
        }
        stages = [
            ("Awaiting results", [OrderStatus.RECEIVED, OrderStatus.IN_PROGRESS], ("priority", "timestamp")),
            ("Awaiting technical validation", [OrderStatus.RESULTED], ("timestamp",)),
            ("Awaiting clinical verification", [OrderStatus.TECHNICALLY_VALIDATED], ("timestamp",)),
        ]
        worklist = reverse("laboratory:results")
        for label, statuses, ordering in stages:
            count = sum(sizes.get(status, 0) for status in statuses)
            if not count:
                continue
            queues.append({
                "label": label,
                "count": count,
                "url": worklist,
                "orders": orders.filter(status__in=statuses)
                          .select_related("patient")
                          .prefetch_related("tests")
                          .order_by(*ordering)[:8],
            })

    # ── Things with a clock on them ──────────────────────────────────────────
    critical = list(
        CriticalValueNotification.objects.pending().select_related("patient", "test")[:8]
    )
    critical_total = CriticalValueNotification.objects.pending().count()
    stat_open = list(
        orders.pending().filter(priority="STAT").select_related("patient")[:5]
    )
    completed_today = orders.filter(status=OrderStatus.COMPLETED, completed_at__gte=today_start)
    turnarounds = [
        order.turnaround_hours for order in completed_today.only("timestamp", "completed_at")
        if order.turnaround_hours is not None
    ]

    context = {
        "queues": queues,
        "critical": critical,
        "critical_count": critical_total,
        "critical_overdue": CriticalValueNotification.objects.overdue().count(),
        "stat_open": stat_open,
        "stat_count": len(stat_open),
        "orders_today": orders.filter(timestamp__gte=today_start).count(),
        "completed_today": completed_today.count(),
        "average_tat": round(sum(turnarounds) / len(turnarounds), 1) if turnarounds else None,
        "unread_messages": Message.objects.filter(recipient=request.user, read=False).count(),
        "low_stock": low_stock_items()[:5],
    }
    return render(request, "operations/dashboard.html", context)


@login_required
@user_passes_test(lambda u: u.is_authenticated and u.is_manager)
def kpi(request):
    """Turnaround, volume and quality indicators over a rolling window."""
    from apps.laboratory.models import Order, Result
    from apps.quality.models import QcRun

    days = int(request.GET.get("days") or 30)
    since = timezone.now() - timedelta(days=days)

    completed = Order.objects.filter(status=OrderStatus.COMPLETED, completed_at__gte=since)
    turnarounds = [o.turnaround_hours for o in completed if o.turnaround_hours is not None]
    turnarounds.sort()

    def percentile(values, fraction):
        if not values:
            return None
        index = min(int(len(values) * fraction), len(values) - 1)
        return round(values[index], 1)

    qc_runs = QcRun.objects.filter(timestamp__gte=since)
    qc_total = qc_runs.count()

    return render(request, "operations/kpi.html", {
        "days": days,
        "orders_received": Order.objects.filter(timestamp__gte=since).count(),
        "orders_completed": completed.count(),
        "tat_median": percentile(turnarounds, 0.5),
        "tat_p90": percentile(turnarounds, 0.9),
        "tat_mean": round(sum(turnarounds) / len(turnarounds), 1) if turnarounds else None,
        "breaches": TatBreach.objects.filter(detected_at__gte=since).count(),
        "qc_total": qc_total,
        "qc_failures": qc_runs.filter(status=QcRun.Status.FAIL).count(),
        "qc_pass_rate": round(
            qc_runs.filter(status=QcRun.Status.PASS).count() / qc_total * 100, 1
        ) if qc_total else None,
        "results_entered": Result.objects.filter(timestamp__gte=since).count(),
        "by_department": completed.values("tests__department__name").annotate(
            count=Count("id", distinct=True)
        ).order_by("-count")[:10],
    })


@login_required
def tat_monitor(request):
    """Orders approaching or past their turnaround target."""
    from apps.laboratory.models import Order

    open_orders = (
        Order.objects.pending().select_related("patient").prefetch_related("tests")
    )
    thresholds = list(TatThreshold.objects.filter(active=True))

    def threshold_for(order):
        """Most specific applicable threshold: test, then department, then global."""
        test_ids = {t.id for t in order.tests.all()}
        department_ids = {t.department_id for t in order.tests.all() if t.department_id}
        for scope in (TatThreshold.Scope.TEST, TatThreshold.Scope.DEPARTMENT, TatThreshold.Scope.GLOBAL):
            for candidate in thresholds:
                if candidate.scope != scope:
                    continue
                if scope == TatThreshold.Scope.TEST and candidate.test_id in test_ids:
                    return candidate
                if scope == TatThreshold.Scope.DEPARTMENT and candidate.department_id in department_ids:
                    return candidate
                if scope == TatThreshold.Scope.GLOBAL:
                    return candidate
        return None

    rows = []
    for order in open_orders[:300]:
        threshold = threshold_for(order)
        elapsed = order.turnaround_hours or 0
        state = "ok"
        if threshold:
            if elapsed >= threshold.breach_hours:
                state = "breach"
            elif elapsed >= threshold.warning_hours:
                state = "warning"
        rows.append({"order": order, "elapsed": round(elapsed, 1), "threshold": threshold, "state": state})

    rows.sort(key=lambda row: row["elapsed"], reverse=True)
    return render(request, "operations/tat.html", {
        "rows": rows,
        "breached": sum(1 for r in rows if r["state"] == "breach"),
        "warning": sum(1 for r in rows if r["state"] == "warning"),
    })


# ── Messaging and feedback ───────────────────────────────────────────────────


@login_required
def messages_view(request):
    form = ops_forms.MessageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.sender = request.user
        message.save()
        django_messages.success(request, "Message sent.")
        return redirect("operations:messages")

    inbox = Message.objects.filter(
        Q(recipient=request.user) | Q(recipient__isnull=True, recipient_department=request.user.department)
    ).select_related("sender")[:50]
    Message.objects.filter(recipient=request.user, read=False).update(read=True)

    return render(request, "operations/messages.html", {
        "form": form,
        "inbox": inbox,
        "sent": Message.objects.filter(sender=request.user).select_related("recipient")[:25],
    })


@login_required
def feedback(request):
    form = ops_forms.FeedbackForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)
        entry.user = request.user
        entry.save()
        django_messages.success(request, "Thank you — your feedback has been recorded.")
        return redirect("operations:feedback")

    entries = Feedback.objects.select_related("user")
    if not request.user.is_manager:
        entries = entries.filter(user=request.user)
    return render(request, "operations/feedback.html", {"form": form, "entries": entries[:50]})


# ── Storage and chain of custody ─────────────────────────────────────────────


@login_required
def storage(request):
    """Freezer map and specimen placement."""
    if request.user.role not in LAB_STAFF:
        django_messages.error(request, "Your role does not permit specimen storage.")
        return redirect("operations:dashboard")

    form = ops_forms.StorageAssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.stored_by = request.user.username
        assignment.save()
        ChainOfCustodyEvent.objects.create(
            specimen=assignment.specimen,
            event_type=ChainOfCustodyEvent.EventType.STORED,
            to_custodian=request.user.username,
            location=assignment.location.path,
        )
        django_messages.success(request, "Specimen stored.")
        return redirect("operations:storage")

    return render(request, "operations/storage.html", {
        "form": form,
        "locations": StorageLocation.objects.filter(active=True).select_related("parent"),
        "assignments": StorageAssignment.objects.filter(removed_at__isnull=True)
                       .select_related("specimen", "location")[:50],
    })


@login_required
def tracking(request):
    """Chain of custody search and timeline."""
    query = (request.GET.get("q") or "").strip()
    events = ChainOfCustodyEvent.objects.select_related("specimen", "specimen__order")

    if query:
        events = events.filter(
            Q(specimen__container_id__icontains=query)
            | Q(specimen__order__accession_number__icontains=query)
        )
    events = events.order_by("-timestamp")[:200]

    return render(request, "operations/tracking.html", {"events": events, "query": query})


# ── Configuration screens ────────────────────────────────────────────────────


class QueueBoardView(DxListView):
    """Orders grouped by the authorisation queue they are waiting in."""

    model = None
    required_roles = LAB_STAFF
    template_name = "operations/queues.html"

    def get(self, request, *args, **kwargs):
        from apps.laboratory.models import AuthorizationQueue, Order

        queues = []
        for queue in AuthorizationQueue.objects.select_related("department"):
            orders = Order.objects.filter(queue=queue).pending().select_related("patient")[:25]
            queues.append({"queue": queue, "orders": orders, "permitted": queue.permits(request.user)})

        unassigned = Order.objects.filter(queue__isnull=True).pending().select_related("patient")[:25]
        return render(request, "operations/queues.html", {"queues": queues, "unassigned": unassigned})


@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.is_admin or u.is_installer))
def backup(request):
    """Backup and maintenance status."""
    from apps.audit.models import AuditEvent
    from apps.audit.protection import is_installed
    from apps.audit.recorder import recorder, spool_path
    from apps.audit.verification import latest_checkpoint

    path = spool_path()
    return render(request, "operations/backup.html", {
        "audit_events": AuditEvent.objects.count(),
        "audit_protection": is_installed(),
        "audit_checkpoint": latest_checkpoint(),
        "recorder_running": recorder.is_running(),
        "queue_depth": recorder.pending(),
        "spool_exists": path.exists() and path.stat().st_size > 0,
        "spool_path": str(path),
    })
