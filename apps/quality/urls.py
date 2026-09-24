"""URL routes for the quality control, equipment and rejection criteria.

Ordering matters here. ``CrudResource.urls()`` ends each resource with a
``<str:pk>/`` pattern, which matches **any** single path segment — so a
resource mounted at a prefix that is a parent of another's will swallow it.
Anything more specific must be listed first, and several entries below are
placed deliberately rather than alphabetically.
"""
from django.urls import path

from apps.common.views import CrudResource
from apps.quality import forms as quality_forms
from apps.quality import views
from apps.quality.models import (
    Equipment, EquipmentLog, QcDefinition, QcMaterial, RejectionCriterion,
)

app_name = "quality"

materials = CrudResource(
    "material", QcMaterial, quality_forms.QcMaterialForm,
    roles=views.LAB_STAFF, title="QC materials", singular="QC material",
    columns=[("Name", "name", ""), ("Lot", "lot_number", "mono"), ("Level", "level", ""),
             ("Expires", "expiration_date", "nowrap"), ("Expired", "is_expired", ""),
             ("Manufacturer", "manufacturer", ""), ("Active", "active", "")],
    search_fields=["name", "lot_number", "manufacturer"],
)

definitions = CrudResource(
    "definition", QcDefinition, quality_forms.QcDefinitionForm,
    roles=views.MANAGERS, title="QC target values", singular="QC target",
    columns=[("Test", "test_code", "mono"), ("Material", "material.name", ""),
             ("Lot", "material.lot_number", "mono"), ("Mean", "mean", ""),
             ("SD", "sd", ""), ("Unit", "unit", "")],
    search_fields=["test_code", "test_name"],
)

equipment = CrudResource(
    "equipment", Equipment, quality_forms.EquipmentForm,
    roles=views.MANAGERS, title="Equipment", singular="equipment",
    subtitle="Maintenance and calibration records — CLIA 42 CFR §493.1254",
    list_template="quality/equipment_list.html",
    columns=[("Name", "name", ""), ("Type", "type", ""), ("Serial", "serial_number", "mono"),
             ("Department", "department.name", ""), ("Status", "status", ""),
             ("Next service", "next_service_date", "nowrap"),
             ("Next calibration", "next_calibration_date", "nowrap"),
             ("Calibration overdue", "calibration_overdue", "")],
    search_fields=["name", "serial_number", "manufacturer"],
)

equipment_log = CrudResource(
    "equipment_log", EquipmentLog, quality_forms.EquipmentLogForm,
    roles=views.LAB_STAFF, title="Equipment log", singular="equipment log entry",
    columns=[("When", "timestamp", "nowrap"), ("Equipment", "equipment.name", ""),
             ("Type", "type", ""), ("Description", "description", ""),
             ("By", "performed_by", ""), ("Outcome", "outcome", "")],
    search_fields=["equipment__name", "description", "performed_by"],
)

criteria = CrudResource(
    "criterion", RejectionCriterion, quality_forms.RejectionCriterionForm,
    roles=views.MANAGERS, title="Specimen rejection criteria", singular="rejection criterion",
    columns=[("Reason", "reason", ""), ("Category", "category", ""),
             ("Description", "description", ""), ("Active", "active", "")],
    search_fields=["reason", "description"],
)

urlpatterns = [
    path("qc/", views.qc, name="qc"),
    *materials.urls("qc/materials/"),
    *definitions.urls("qc/targets/"),
    # Listed before `equipment`, whose `<pk>/` pattern would shadow them.
    *equipment_log.urls("equipment/log/"),
    *equipment.urls("equipment/"),
    *criteria.urls("criteria/"),
]
