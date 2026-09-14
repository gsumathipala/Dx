from django.urls import path

from apps.audit import views

app_name = "audit"

urlpatterns = [
    path("", views.trail, name="trail"),
    path("event/<int:sequence>/", views.event_detail, name="event_detail"),
    path("history/<str:entity_type>/<str:entity_id>/", views.entity_history, name="entity_history"),
    path("integrity/", views.integrity, name="integrity"),
    path("integrity/verify/", views.run_verification, name="run_verification"),
    path("integrity/alerts/<int:alert_id>/acknowledge/", views.acknowledge, name="acknowledge"),
    path("export.csv", views.export_csv, name="export_csv"),
    path("api/verify/", views.verify_api, name="verify_api"),
]
