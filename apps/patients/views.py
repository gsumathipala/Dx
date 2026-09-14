"""Patient registry and the consolidated patient record."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES, Role
from apps.common.views import DxCreateView, DxListView, DxUpdateView
from apps.patients.forms import PatientForm
from apps.patients.models import Patient

MANAGERS = tuple(MANAGEMENT_ROLES)
STAFF = tuple(LAB_STAFF_ROLES) + (Role.CLERK, Role.PHLEBOTOMIST)


class PatientListView(DxListView):
    model = Patient
    required_roles = None
    page_title = "Patients"
    search_fields = ["first_name", "last_name", "mrn", "phone", "email"]
    columns = [
        ("MRN", "mrn", "mono"), ("Name", "full_name", ""),
        ("Date of birth", "dob", "nowrap"), ("Age", "age_display", ""),
        ("Sex", "get_gender_display", ""), ("Phone", "phone", ""),
    ]
    create_url_name = "patients:create"
    update_url_name = "patients:update"
    empty_message = "No patients registered yet."


class PatientAdminListView(PatientListView):
    """Manager view — same list, with the administrative actions enabled."""

    required_roles = MANAGERS
    page_title = "Patient data administration"
    page_subtitle = "Demographic corrections are recorded against your account in the audit trail."


class PatientCreateView(DxCreateView):
    model = Patient
    form_class = PatientForm
    required_roles = STAFF
    page_title = "patient"
    success_url = reverse_lazy("patients:list")


class PatientUpdateView(DxUpdateView):
    model = Patient
    form_class = PatientForm
    required_roles = MANAGERS
    page_title = "patient"
    success_url = reverse_lazy("patients:list")


@login_required
def patient_detail(request, pk):
    """Consolidated patient record: demographics, orders, results, consents.

    Viewing this page is recorded by ``PHIAccessLogMiddleware`` for HIPAA
    disclosure accounting.
    """
    from apps.audit.models import AuditEvent
    from apps.clinical.models import CriticalValueNotification
    from apps.laboratory.models import Order, Result

    patient = get_object_or_404(Patient, pk=pk)
    orders = (
        Order.objects.filter(patient=patient)
        .prefetch_related("tests", "results")
        .order_by("-timestamp")[:50]
    )

    context = {
        "patient": patient,
        "orders": orders,
        "order_count": Order.objects.filter(patient=patient).count(),
        "critical_values": CriticalValueNotification.objects.filter(patient=patient)[:10],
        "consents": patient.consents.all(),
        "disclosures": patient.disclosures.all()[:10],
        "audit_events": AuditEvent.objects.for_entity("patients.Patient", patient.pk)[:15],
        "entity_type": "patients.Patient",
    }
    return render(request, "patients/detail.html", context)


@login_required
def patient_trend(request, pk):
    """Cumulative view of one patient's numeric results over time."""
    from apps.laboratory.models import Result, TestDefinition

    patient = get_object_or_404(Patient, pk=pk)
    test_codes = request.GET.getlist("test")

    results = (
        Result.objects.filter(order__patient=patient, numeric_value__isnull=False)
        .select_related("test", "order")
        .order_by("test__code", "order__timestamp")
    )
    if test_codes:
        results = results.filter(test__code__in=test_codes)

    series: dict[str, list] = {}
    for result in results:
        if result.test is None:
            continue
        series.setdefault(result.test.code, []).append(result)

    return render(request, "patients/trend.html", {
        "patient": patient,
        "series": series,
        "available_tests": TestDefinition.objects.filter(
            results__order__patient=patient
        ).distinct().order_by("code"),
        "selected": test_codes,
    })
