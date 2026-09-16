from django.urls import path

from apps.common.views import CrudResource
from apps.laboratory import forms as lab_forms
from apps.laboratory import views
from apps.laboratory.models import (
    AuthorizationQueue, PhlebotomySchedule, RetentionPolicy, TestDefinition,
)

app_name = "laboratory"

phlebotomy = CrudResource(
    "phlebotomy", PhlebotomySchedule, lab_forms.PhlebotomyForm,
    roles=views.ACCESSIONING_ROLES + (views.Role.PHLEBOTOMIST,),
    title="Phlebotomy rounds", singular="phlebotomy round",
    columns=[("Scheduled", "scheduled_at", "nowrap"), ("Patient", "patient.full_name", ""),
             ("MRN", "patient.mrn", "mono"), ("Ward", "ward_location", ""),
             ("Type", "collection_type", ""), ("Assigned", "assigned_to.name", ""),
             ("Status", "status", "")],
    search_fields=["patient__mrn", "patient__last_name", "ward_location"],
    filter_fields={"status": "status"},
)

tests = CrudResource(
    "test", TestDefinition, lab_forms.TestDefinitionForm,
    roles=views.MANAGERS, title="Test definitions", singular="test definition",
    subtitle="The test catalogue, its units, reference intervals and critical limits.",
    columns=[("Code", "code", "mono"), ("Name", "name", ""),
             ("Department", "department.name", ""), ("Units", "units", ""),
             ("Reference", "reference_display", "nowrap"), ("TAT (h)", "tat_hours", ""),
             ("LOINC", "loinc_code", "mono"), ("Active", "active", "")],
    search_fields=["code", "name", "loinc_code"],
)

queues = CrudResource(
    "queue", AuthorizationQueue, lab_forms.QueueForm,
    roles=views.MANAGERS, title="Authorisation queues", singular="queue",
    columns=[("Name", "name", ""), ("Department", "department.name", ""),
             ("Allowed roles", "allowed_roles", ""), ("Created", "created_at", "nowrap")],
    search_fields=["name", "description"],
    on_create=lambda view, form: setattr(form.instance, "created_by", view.request.user.username),
)

retention = CrudResource(
    "retention", RetentionPolicy, lab_forms.RetentionPolicyForm,
    roles=views.MANAGERS, title="Sample retention policies", singular="retention policy",
    subtitle="How long each specimen type is kept before disposal.",
    columns=[("Specimen type", "specimen_type", ""), ("Days", "retention_days", ""),
             ("Storage", "temperature", ""), ("Disposal", "disposal_method", ""),
             ("Active", "active", "")],
    search_fields=["specimen_type"],
)

urlpatterns = [
    path("accessioning/", views.accessioning, name="accessioning"),
    path("receiving/", views.receiving, name="receiving"),
    path("results/", views.results_worklist, name="results"),
    path("results/verify-batch/", views.verify_batch_view, name="verify_batch"),
    path("results/<str:pk>/", views.result_entry, name="result_entry"),
    path("labels/<str:pk>/", views.print_labels, name="print_labels"),

    *phlebotomy.urls("phlebotomy/"),
    *tests.urls("config/tests/"),
    *queues.urls("config/queues/"),
    *retention.urls("config/retention/"),
]
