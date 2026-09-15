from django.urls import path

from apps.common.views import CrudResource
from apps.operations import forms as ops_forms
from apps.operations import views
from apps.operations.models import (
    RoutingAssignment, RoutingRule, StorageLocation, SystemAlert, SystemSetting,
    TatThreshold, Worksheet, Workstation,
)
from django.db.models import Count, Q

app_name = "operations"

worksheets = CrudResource(
    "worksheet", Worksheet, ops_forms.WorksheetForm,
    roles=views.LAB_STAFF, title="Worksheets", singular="worksheet",
    columns=[("Name", "name", ""), ("Department", "department.name", ""),
             ("Status", "status", ""), ("Created", "created_at", "nowrap"),
             ("By", "created_by", "")],
    search_fields=["name"],
    on_create=lambda view, form: setattr(form.instance, "created_by", view.request.user.username),
)

workstations = CrudResource(
    "workstation", Workstation, ops_forms.WorkstationForm,
    roles=views.MANAGERS, title="Workstations", singular="workstation",
    # Counted in SQL; the equivalent model properties issue one COUNT per row.
    annotations={
        "queued_count": Count("assignments", filter=Q(assignments__status=RoutingAssignment.Status.PENDING)),
        "active_count": Count("assignments", filter=Q(assignments__status=RoutingAssignment.Status.IN_PROGRESS)),
    },
    columns=[("Name", "name", ""), ("Department", "department.name", ""),
             ("Status", "status", ""), ("Queued", "queued_count", ""),
             ("In progress", "active_count", ""), ("Capacity/h", "max_throughput", ""),
             ("Active", "active", "")],
    search_fields=["name"],
)

routing = CrudResource(
    "routing", RoutingRule, ops_forms.RoutingRuleForm,
    roles=views.MANAGERS, title="Routing rules", singular="routing rule",
    columns=[("Test", "test.code", "mono"), ("Department", "department.name", ""),
             ("Specimen type", "specimen_type", ""), ("Priority", "priority", ""),
             ("Active", "active", "")],
)

tat_thresholds = CrudResource(
    "tat_threshold", TatThreshold, ops_forms.TatThresholdForm,
    roles=views.MANAGERS, title="Turnaround time thresholds", singular="TAT threshold",
    columns=[("Scope", "get_scope_display", ""), ("Test", "test.code", "mono"),
             ("Department", "department.name", ""), ("Target (h)", "target_hours", ""),
             ("Warning (h)", "warning_hours", ""), ("Breach (h)", "breach_hours", ""),
             ("Priority", "priority", ""), ("Active", "active", "")],
)

storage_locations = CrudResource(
    "storage_location", StorageLocation, ops_forms.StorageLocationForm,
    roles=views.LAB_STAFF, title="Storage locations", singular="storage location",
    annotations={
        "occupied_count": Count("stored_specimens", filter=Q(stored_specimens__removed_at__isnull=True)),
    },
    # `path` walks up the parent chain, so fetch two levels with the row.
    select_related_extra=("parent__parent",),
    columns=[("Name", "name", ""), ("Kind", "get_kind_display", ""), ("Path", "path", "muted"),
             ("Temperature", "temperature", ""), ("Capacity", "capacity", ""),
             ("Occupied", "occupied_count", "")],
    search_fields=["name"],
)

alerts = CrudResource(
    "alert", SystemAlert, ops_forms.SystemAlertForm,
    roles=views.MANAGERS, title="System alerts", singular="system alert",
    columns=[("Message", "message", ""), ("Type", "type", ""),
             ("Created", "created_at", "nowrap"), ("Expires", "expires_at", "nowrap"),
             ("Active", "active", "")],
)

settings_resource = CrudResource(
    "setting", SystemSetting, ops_forms.SystemSettingForm,
    roles=views.MANAGERS, title="Configuration", singular="setting",
    subtitle="Changes here are recorded in the audit trail and may require a change control record.",
    columns=[("Key", "key", "mono"), ("Value", "value", ""), ("Description", "description", "muted")],
    search_fields=["key", "description"],
)

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("search/", views.search, name="search"),
    path("settings/", views.settings_index, name="settings_index"),
    path("dashboard/", views.dashboard, name="dashboard_alias"),
    path("kpi/", views.kpi, name="kpi"),
    path("tat/", views.tat_monitor, name="tat"),
    path("messages/", views.messages_view, name="messages"),
    path("feedback/", views.feedback, name="feedback"),
    path("tracking/", views.tracking, name="tracking"),
    path("queues/", views.QueueBoardView.as_view(), name="queues"),
    path("backup/", views.backup, name="backup"),

    # Listed before the storage-location resource so "storage/" is not shadowed.
    path("storage/", views.storage, name="storage"),
    *storage_locations.urls("storage/locations/"),

    *worksheets.urls("worksheets/"),
    *workstations.urls("workstations/"),
    *routing.urls("routing/"),
    *tat_thresholds.urls("config/tat/"),
    *alerts.urls("config/alerts/"),
    *settings_resource.urls("config/settings/"),
]
