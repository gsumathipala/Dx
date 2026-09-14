from django.urls import path

from apps.operations import views

app_name = "operations"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/", views.dashboard, name="dashboard_alias"),
    path("kpi/", views.kpi, name="kpi"),
    path("tat/", views.tat_monitor, name="tat"),

    path("messages/", views.messages_view, name="messages"),
    path("feedback/", views.feedback, name="feedback"),

    path("storage/", views.storage, name="storage"),
    path("storage/locations/", views.StorageLocationListView.as_view(), name="storage_locations"),
    path("storage/locations/new/", views.StorageLocationCreateView.as_view(), name="storage_location_create"),
    path("storage/locations/<str:pk>/", views.StorageLocationUpdateView.as_view(), name="storage_location_update"),
    path("tracking/", views.tracking, name="tracking"),

    path("queues/", views.QueueBoardView.as_view(), name="queues"),
    path("worksheets/", views.WorksheetListView.as_view(), name="worksheets"),
    path("worksheets/new/", views.WorksheetCreateView.as_view(), name="worksheet_create"),
    path("worksheets/<str:pk>/", views.WorksheetUpdateView.as_view(), name="worksheet_update"),

    path("workstations/", views.WorkstationListView.as_view(), name="workstations"),
    path("workstations/new/", views.WorkstationCreateView.as_view(), name="workstation_create"),
    path("workstations/<str:pk>/", views.WorkstationUpdateView.as_view(), name="workstation_update"),

    path("routing/", views.RoutingRuleListView.as_view(), name="routing"),
    path("routing/new/", views.RoutingRuleCreateView.as_view(), name="routing_create"),
    path("routing/<str:pk>/", views.RoutingRuleUpdateView.as_view(), name="routing_update"),

    path("config/tat/", views.TatThresholdListView.as_view(), name="tat_thresholds"),
    path("config/tat/new/", views.TatThresholdCreateView.as_view(), name="tat_threshold_create"),
    path("config/tat/<str:pk>/", views.TatThresholdUpdateView.as_view(), name="tat_threshold_update"),

    path("config/alerts/", views.AlertListView.as_view(), name="alert_list"),
    path("config/alerts/new/", views.AlertCreateView.as_view(), name="alert_create"),
    path("config/alerts/<str:pk>/", views.AlertUpdateView.as_view(), name="alert_update"),

    path("config/settings/", views.SettingListView.as_view(), name="settings"),
    path("config/settings/new/", views.SettingCreateView.as_view(), name="setting_create"),
    path("config/settings/<str:pk>/", views.SettingUpdateView.as_view(), name="setting_update"),

    path("backup/", views.backup, name="backup"),
]
