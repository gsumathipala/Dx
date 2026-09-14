"""Quality control, Levey-Jennings review and instrument records."""
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES
from apps.common.views import DxCreateView, DxListView, DxUpdateView
from apps.quality import forms as quality_forms
from apps.quality.models import (
    Equipment, EquipmentLog, QcDefinition, QcMaterial, QcRun,
    RejectionCriterion, evaluate_westgard,
)

LAB_STAFF = tuple(LAB_STAFF_ROLES)
MANAGERS = tuple(MANAGEMENT_ROLES)


@login_required
def qc(request):
    """Enter a control value and review recent runs.

    A failing run automatically raises a nonconformance, because CLIA requires
    QC failures to be investigated and the corrective action documented — an
    unrecorded failure is exactly what an inspection looks for.
    """
    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit quality control entry.")
        return redirect("operations:dashboard")

    form = quality_forms.QcRunForm(request.POST or None, initial={"performed_by": request.user.username})

    if request.method == "POST" and form.is_valid():
        run = form.save(commit=False)
        history = list(
            QcRun.objects.filter(definition=run.definition)
            .order_by("-timestamp")
            .values_list("value", flat=True)[:12]
        )
        run.status, run.result_flags = evaluate_westgard(run.definition, run.value, history)
        run.z_score = run.definition.z_score(run.value)
        run.save()

        if run.status == QcRun.Status.FAIL:
            from apps.compliance.models import CorrectiveAction
            from apps.compliance.services import raise_capa

            capa = raise_capa(
                title=f"QC failure: {run.definition.test_code} ({', '.join(run.result_flags)})",
                category=CorrectiveAction.Category.QC_FAILURE,
                description=(
                    f"Control value {run.value} {run.definition.unit} on "
                    f"{run.definition.material} violated {', '.join(run.result_flags)}. "
                    f"Target mean {run.definition.mean}, SD {run.definition.sd}."
                ),
                raised_by=request.user,
                severity=CorrectiveAction.Severity.HIGH,
                linked_entity_type="quality.QcRun",
                linked_entity_id=run.pk,
            )
            run.corrective_action = capa
            run.accepted = False
            run.save(update_fields=["corrective_action", "accepted"])
            messages.error(
                request,
                f"QC FAILED ({', '.join(run.result_flags)}). Patient results for "
                f"{run.definition.test_code} are blocked until acceptable QC is recorded. "
                f"Nonconformance {capa.reference} has been opened.",
            )
        elif run.status == QcRun.Status.WARNING:
            messages.warning(request, f"QC warning ({', '.join(run.result_flags)}). Review before reporting.")
        else:
            messages.success(request, "QC run recorded — within acceptable limits.")
        return redirect("quality:qc")

    since = timezone.now() - timedelta(days=30)
    definitions = QcDefinition.objects.select_related("material", "test").order_by("test_code")

    charts = []
    for definition in definitions[:12]:
        runs = list(
            QcRun.objects.filter(definition=definition, timestamp__gte=since).order_by("timestamp")
        )
        if runs:
            charts.append({"definition": definition, "runs": runs,
                           "points": _levey_jennings_points(definition, runs)})

    return render(request, "quality/qc.html", {
        "form": form,
        "charts": charts,
        "recent": QcRun.objects.select_related("definition").order_by("-timestamp")[:25],
        "failing": QcRun.objects.filter(
            status=QcRun.Status.FAIL, timestamp__gte=since, corrective_action__isnull=True
        ).select_related("definition"),
    })


def _levey_jennings_points(definition, runs) -> list[dict]:
    """Position each run on a -4 to +4 SD scale for the chart."""
    points = []
    for index, run in enumerate(runs):
        z = definition.z_score(run.value)
        if z is None:
            continue
        clamped = max(-4.0, min(4.0, z))
        points.append({
            "run": run,
            "z": z,
            "x": (index / max(len(runs) - 1, 1)) * 100,
            "y": 50 - (clamped / 4.0) * 45,
        })
    return points


class QcMaterialListView(DxListView):
    model = QcMaterial
    required_roles = LAB_STAFF
    page_title = "QC materials"
    search_fields = ["name", "lot_number", "manufacturer"]
    columns = [
        ("Name", "name", ""), ("Lot", "lot_number", "mono"), ("Level", "level", ""),
        ("Expires", "expiration_date", "nowrap"), ("Expired", "is_expired", ""),
        ("Manufacturer", "manufacturer", ""), ("Active", "active", ""),
    ]
    create_url_name = "quality:material_create"
    update_url_name = "quality:material_update"


class QcMaterialCreateView(DxCreateView):
    model = QcMaterial
    form_class = quality_forms.QcMaterialForm
    required_roles = LAB_STAFF
    page_title = "QC material"
    success_url = reverse_lazy("quality:material_list")


class QcMaterialUpdateView(DxUpdateView):
    model = QcMaterial
    form_class = quality_forms.QcMaterialForm
    required_roles = LAB_STAFF
    page_title = "QC material"
    success_url = reverse_lazy("quality:material_list")


class QcDefinitionListView(DxListView):
    model = QcDefinition
    required_roles = MANAGERS
    page_title = "QC target values"
    search_fields = ["test_code", "test_name"]
    columns = [
        ("Test", "test_code", "mono"), ("Material", "material.name", ""),
        ("Lot", "material.lot_number", "mono"), ("Mean", "mean", ""),
        ("SD", "sd", ""), ("Unit", "unit", ""),
    ]
    create_url_name = "quality:definition_create"
    update_url_name = "quality:definition_update"

    def get_queryset(self):
        return super().get_queryset().select_related("material", "test")


class QcDefinitionCreateView(DxCreateView):
    model = QcDefinition
    form_class = quality_forms.QcDefinitionForm
    required_roles = MANAGERS
    page_title = "QC target"
    success_url = reverse_lazy("quality:definition_list")


class QcDefinitionUpdateView(DxUpdateView):
    model = QcDefinition
    form_class = quality_forms.QcDefinitionForm
    required_roles = MANAGERS
    page_title = "QC target"
    success_url = reverse_lazy("quality:definition_list")


# ── Equipment ────────────────────────────────────────────────────────────────


class EquipmentListView(DxListView):
    model = Equipment
    required_roles = None
    template_name = "quality/equipment_list.html"
    page_title = "Equipment"
    page_subtitle = "Maintenance and calibration records — CLIA 42 CFR §493.1254"
    search_fields = ["name", "serial_number", "manufacturer"]
    columns = [
        ("Name", "name", ""), ("Type", "type", ""), ("Serial", "serial_number", "mono"),
        ("Department", "department.name", ""), ("Status", "status", ""),
        ("Next service", "next_service_date", "nowrap"),
        ("Next calibration", "next_calibration_date", "nowrap"),
        ("Calibration overdue", "calibration_overdue", ""),
    ]
    create_url_name = "quality:equipment_create"
    update_url_name = "quality:equipment_update"

    def get_queryset(self):
        return super().get_queryset().select_related("department")


class EquipmentCreateView(DxCreateView):
    model = Equipment
    form_class = quality_forms.EquipmentForm
    required_roles = MANAGERS
    page_title = "equipment"
    success_url = reverse_lazy("quality:equipment")


class EquipmentUpdateView(DxUpdateView):
    model = Equipment
    form_class = quality_forms.EquipmentForm
    required_roles = MANAGERS
    page_title = "equipment"
    success_url = reverse_lazy("quality:equipment")


class EquipmentLogListView(DxListView):
    model = EquipmentLog
    required_roles = None
    page_title = "Equipment log"
    search_fields = ["equipment__name", "description", "performed_by"]
    columns = [
        ("When", "timestamp", "nowrap"), ("Equipment", "equipment.name", ""),
        ("Type", "type", ""), ("Description", "description", ""),
        ("By", "performed_by", ""), ("Outcome", "outcome", ""),
    ]
    create_url_name = "quality:equipment_log_create"

    def get_queryset(self):
        return super().get_queryset().select_related("equipment")


class EquipmentLogCreateView(DxCreateView):
    model = EquipmentLog
    form_class = quality_forms.EquipmentLogForm
    required_roles = LAB_STAFF
    page_title = "equipment log entry"
    success_url = reverse_lazy("quality:equipment_log")


class RejectionCriterionListView(DxListView):
    model = RejectionCriterion
    required_roles = MANAGERS
    page_title = "Specimen rejection criteria"
    search_fields = ["reason", "description"]
    columns = [
        ("Reason", "reason", ""), ("Category", "category", ""),
        ("Description", "description", ""), ("Active", "active", ""),
    ]
    create_url_name = "quality:criteria_create"
    update_url_name = "quality:criteria_update"


class RejectionCriterionCreateView(DxCreateView):
    model = RejectionCriterion
    form_class = quality_forms.RejectionCriterionForm
    required_roles = MANAGERS
    page_title = "rejection criterion"
    success_url = reverse_lazy("quality:criteria_list")


class RejectionCriterionUpdateView(DxUpdateView):
    model = RejectionCriterion
    form_class = quality_forms.RejectionCriterionForm
    required_roles = MANAGERS
    page_title = "rejection criterion"
    success_url = reverse_lazy("quality:criteria_list")
