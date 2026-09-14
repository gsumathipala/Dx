"""Dashboard, KPIs, messaging, storage, custody tracking and configuration."""
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES, OrderStatus, Role
from apps.common.views import DxCreateView, DxListView, DxUpdateView
from apps.operations import forms as ops_forms
from apps.operations.models import (
    ChainOfCustodyEvent, Feedback, Message, RoutingRule, StorageAssignment,
    StorageLocation, SystemAlert, SystemSetting, TatBreach, TatThreshold,
    Worksheet, Workstation,
)

LAB_STAFF = tuple(LAB_STAFF_ROLES)
MANAGERS = tuple(MANAGEMENT_ROLES)
ADMIN_ONLY = (Role.ADMIN,)


def healthz(request):
    """Liveness probe — also reports whether the audit recorder is running."""
    from apps.audit.recorder import recorder

    return JsonResponse({
        "status": "ok",
        "audit_recorder": "running" if recorder.is_running() else "stopped",
        "audit_queue_depth": recorder.pending(),
    })


@login_required
def dashboard(request):
    """Operational overview for the signed-in user's role."""
    from apps.clinical.models import CriticalValueNotification
    from apps.inventory.services import low_stock_items
    from apps.laboratory.models import Order

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    orders = Order.objects.all()
    completed_today = orders.filter(status=OrderStatus.COMPLETED, completed_at__gte=today_start)

    turnarounds = [
        order.turnaround_hours for order in completed_today.only("timestamp", "completed_at")
        if order.turnaround_hours is not None
    ]

    context = {
        "orders_today": orders.filter(timestamp__gte=today_start).count(),
        "pending": orders.pending().count(),
        "completed_today": completed_today.count(),
        "stat_pending": orders.pending().filter(priority="STAT").count(),
        "average_tat": round(sum(turnarounds) / len(turnarounds), 1) if turnarounds else None,
        "by_status": orders.values("status").annotate(count=Count("id")).order_by("-count"),
        "critical_pending": CriticalValueNotification.objects.filter(
            status=CriticalValueNotification.Status.PENDING
        ).select_related("patient", "test")[:8],
        "recent_orders": orders.select_related("patient").order_by("-timestamp")[:12],
        "unread_messages": Message.objects.filter(recipient=request.user, read=False).count(),
        "low_stock": low_stock_items()[:8],
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


class WorksheetListView(DxListView):
    model = Worksheet
    required_roles = LAB_STAFF
    page_title = "Worksheets"
    search_fields = ["name"]
    columns = [
        ("Name", "name", ""), ("Department", "department.name", ""),
        ("Status", "status", ""), ("Created", "created_at", "nowrap"),
        ("By", "created_by", ""),
    ]
    create_url_name = "operations:worksheet_create"
    update_url_name = "operations:worksheet_update"


class WorksheetCreateView(DxCreateView):
    model = Worksheet
    form_class = ops_forms.WorksheetForm
    required_roles = LAB_STAFF
    page_title = "worksheet"
    success_url = reverse_lazy("operations:worksheets")

    def form_valid(self, form):
        form.instance.created_by = self.request.user.username
        return super().form_valid(form)


class WorksheetUpdateView(DxUpdateView):
    model = Worksheet
    form_class = ops_forms.WorksheetForm
    required_roles = LAB_STAFF
    page_title = "worksheet"
    success_url = reverse_lazy("operations:worksheets")


class WorkstationListView(DxListView):
    model = Workstation
    required_roles = MANAGERS
    page_title = "Workstations"
    search_fields = ["name"]
    columns = [
        ("Name", "name", ""), ("Department", "department.name", ""),
        ("Status", "status", ""), ("Queued", "queued_tests", ""),
        ("In progress", "current_tests", ""), ("Capacity/h", "max_throughput", ""),
        ("Active", "active", ""),
    ]
    create_url_name = "operations:workstation_create"
    update_url_name = "operations:workstation_update"


class WorkstationCreateView(DxCreateView):
    model = Workstation
    form_class = ops_forms.WorkstationForm
    required_roles = MANAGERS
    page_title = "workstation"
    success_url = reverse_lazy("operations:workstations")


class WorkstationUpdateView(DxUpdateView):
    model = Workstation
    form_class = ops_forms.WorkstationForm
    required_roles = MANAGERS
    page_title = "workstation"
    success_url = reverse_lazy("operations:workstations")


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


class RoutingRuleListView(DxListView):
    model = RoutingRule
    required_roles = MANAGERS
    page_title = "Routing rules"
    columns = [
        ("Test", "test.code", "mono"), ("Department", "department.name", ""),
        ("Specimen type", "specimen_type", ""), ("Priority", "priority", ""),
        ("Active", "active", ""),
    ]
    create_url_name = "operations:routing_create"
    update_url_name = "operations:routing_update"


class RoutingRuleCreateView(DxCreateView):
    model = RoutingRule
    form_class = ops_forms.RoutingRuleForm
    required_roles = MANAGERS
    page_title = "routing rule"
    success_url = reverse_lazy("operations:routing")


class RoutingRuleUpdateView(DxUpdateView):
    model = RoutingRule
    form_class = ops_forms.RoutingRuleForm
    required_roles = MANAGERS
    page_title = "routing rule"
    success_url = reverse_lazy("operations:routing")


class TatThresholdListView(DxListView):
    model = TatThreshold
    required_roles = MANAGERS
    page_title = "Turnaround time thresholds"
    columns = [
        ("Scope", "get_scope_display", ""), ("Test", "test.code", "mono"),
        ("Department", "department.name", ""), ("Target (h)", "target_hours", ""),
        ("Warning (h)", "warning_hours", ""), ("Breach (h)", "breach_hours", ""),
        ("Priority", "priority", ""), ("Active", "active", ""),
    ]
    create_url_name = "operations:tat_threshold_create"
    update_url_name = "operations:tat_threshold_update"


class TatThresholdCreateView(DxCreateView):
    model = TatThreshold
    form_class = ops_forms.TatThresholdForm
    required_roles = MANAGERS
    page_title = "TAT threshold"
    success_url = reverse_lazy("operations:tat_thresholds")


class TatThresholdUpdateView(DxUpdateView):
    model = TatThreshold
    form_class = ops_forms.TatThresholdForm
    required_roles = MANAGERS
    page_title = "TAT threshold"
    success_url = reverse_lazy("operations:tat_thresholds")


class StorageLocationListView(DxListView):
    model = StorageLocation
    required_roles = LAB_STAFF
    page_title = "Storage locations"
    search_fields = ["name"]
    columns = [
        ("Name", "name", ""), ("Kind", "get_kind_display", ""), ("Path", "path", "muted"),
        ("Temperature", "temperature", ""), ("Capacity", "capacity", ""),
        ("Occupied", "occupancy", ""), ("Full", "is_full", ""),
    ]
    create_url_name = "operations:storage_location_create"
    update_url_name = "operations:storage_location_update"


class StorageLocationCreateView(DxCreateView):
    model = StorageLocation
    form_class = ops_forms.StorageLocationForm
    required_roles = LAB_STAFF
    page_title = "storage location"
    success_url = reverse_lazy("operations:storage_locations")


class StorageLocationUpdateView(DxUpdateView):
    model = StorageLocation
    form_class = ops_forms.StorageLocationForm
    required_roles = LAB_STAFF
    page_title = "storage location"
    success_url = reverse_lazy("operations:storage_locations")


class AlertListView(DxListView):
    model = SystemAlert
    required_roles = MANAGERS
    page_title = "System alerts"
    columns = [
        ("Message", "message", ""), ("Type", "type", ""),
        ("Created", "created_at", "nowrap"), ("Expires", "expires_at", "nowrap"),
        ("Active", "active", ""),
    ]
    create_url_name = "operations:alert_create"
    update_url_name = "operations:alert_update"


class AlertCreateView(DxCreateView):
    model = SystemAlert
    form_class = ops_forms.SystemAlertForm
    required_roles = MANAGERS
    page_title = "system alert"
    success_url = reverse_lazy("operations:alert_list")


class AlertUpdateView(DxUpdateView):
    model = SystemAlert
    form_class = ops_forms.SystemAlertForm
    required_roles = MANAGERS
    page_title = "system alert"
    success_url = reverse_lazy("operations:alert_list")


class SettingListView(DxListView):
    model = SystemSetting
    required_roles = MANAGERS
    page_title = "Configuration"
    page_subtitle = "Changes here are recorded in the audit trail and may require a change control record."
    search_fields = ["key", "description"]
    columns = [("Key", "key", "mono"), ("Value", "value", ""), ("Description", "description", "muted")]
    create_url_name = "operations:setting_create"
    update_url_name = "operations:setting_update"


class SettingCreateView(DxCreateView):
    model = SystemSetting
    form_class = ops_forms.SystemSettingForm
    required_roles = MANAGERS
    page_title = "setting"
    success_url = reverse_lazy("operations:settings")


class SettingUpdateView(DxUpdateView):
    model = SystemSetting
    form_class = ops_forms.SystemSettingForm
    required_roles = MANAGERS
    page_title = "setting"
    success_url = reverse_lazy("operations:settings")


@login_required
@user_passes_test(lambda u: u.is_authenticated and u.is_admin)
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
