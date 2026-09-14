"""Regulatory compliance screens."""
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES, Role
from apps.common.views import DxCreateView, DxListView, DxUpdateView
from apps.compliance import forms as compliance_forms
from apps.compliance.models import (
    ChangeControl, CorrectiveAction, DisclosureAccounting, MethodValidation,
    PHIAccessLog, ProficiencyResult, ProficiencySurvey, RetentionSchedule,
    RiskAssessment, TrainingRecord,
)
from apps.compliance.services import next_capa_reference, record_password_change

MANAGERS = tuple(MANAGEMENT_ROLES)
LAB_STAFF = tuple(LAB_STAFF_ROLES)
ADMIN_ONLY = (Role.ADMIN,)


# ── Password change (enforced by RegulatorySessionMiddleware) ────────────────


@login_required
def password_change(request):
    """Change password, honouring the reuse and complexity rules."""
    form = compliance_forms.PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        request.user.set_password(form.cleaned_data["new_password"])
        request.user.save(update_fields=["password"])
        record_password_change(request.user)
        update_session_auth_hash(request, request.user)
        messages.success(request, "Your password has been changed.")
        return redirect("operations:dashboard")

    return render(request, "compliance/password_change.html", {"form": form})


# ── Compliance dashboard ─────────────────────────────────────────────────────


@login_required
@user_passes_test(lambda u: u.is_authenticated and u.is_manager)
def dashboard(request):
    """A single view of every outstanding regulatory obligation."""
    from apps.accounts.models import UserCompetency
    from apps.audit.models import AuditEvent
    from apps.audit.verification import latest_checkpoint, open_alerts
    from apps.clinical.models import CriticalValueNotification, EpidemiologyNotification
    from apps.quality.models import Equipment, QcRun
    from apps.reporting.models import ControlledDocument

    today = timezone.localdate()
    soon = today + timedelta(days=30)

    outstanding_critical = CriticalValueNotification.objects.filter(
        status=CriticalValueNotification.Status.PENDING
    )

    context = {
        "capa_open": CorrectiveAction.objects.exclude(status=CorrectiveAction.Status.CLOSED).count(),
        "capa_overdue": sum(1 for c in CorrectiveAction.objects.exclude(
            status=CorrectiveAction.Status.CLOSED) if c.is_overdue),
        "pt_overdue": sum(1 for s in ProficiencySurvey.objects.filter(submitted_date__isnull=True)
                          if s.is_overdue),
        "pt_unacceptable": ProficiencyResult.objects.filter(
            grade=ProficiencyResult.Grade.UNACCEPTABLE, corrective_action__isnull=True
        ).count(),
        "competency_expiring": UserCompetency.objects.filter(
            status=UserCompetency.Status.ACTIVE, expiry_date__lte=soon
        ).select_related("user", "test")[:10],
        "competency_expired": UserCompetency.objects.filter(
            status=UserCompetency.Status.ACTIVE, expiry_date__lt=today
        ).count(),
        "validations_pending": MethodValidation.objects.filter(
            status=MethodValidation.Status.IN_PROGRESS
        ).count(),
        "documents_review_overdue": [
            doc for doc in ControlledDocument.objects.filter(
                status=ControlledDocument.Status.ACTIVE, review_due__lt=today
            )[:10]
        ],
        "calibration_overdue": [
            item for item in Equipment.objects.filter(active=True) if item.calibration_overdue
        ][:10],
        "qc_failures": QcRun.objects.filter(
            status=QcRun.Status.FAIL, timestamp__gte=timezone.now() - timedelta(days=7),
            corrective_action__isnull=True,
        ).select_related("definition")[:10],
        "critical_outstanding": outstanding_critical.count(),
        "critical_overdue": sum(1 for n in outstanding_critical if n.is_overdue),
        "epi_overdue": sum(1 for n in EpidemiologyNotification.objects.exclude(
            status__in=[EpidemiologyNotification.Status.SUBMITTED,
                        EpidemiologyNotification.Status.CLOSED]) if n.is_overdue),
        "risks_high": [r for r in RiskAssessment.objects.exclude(
            status=RiskAssessment.Status.CLOSED) if r.rating == "High"][:10],
        "changes_open": ChangeControl.objects.exclude(
            status__in=[ChangeControl.Status.VERIFIED, ChangeControl.Status.REJECTED]
        ).count(),
        "audit_events": AuditEvent.objects.count(),
        "audit_checkpoint": latest_checkpoint(),
        "audit_alerts": open_alerts().count(),
        "retention": RetentionSchedule.objects.filter(active=True),
    }
    return render(request, "compliance/dashboard.html", context)


# ── CAPA ─────────────────────────────────────────────────────────────────────


class CapaListView(DxListView):
    model = CorrectiveAction
    required_roles = LAB_STAFF
    page_title = "Corrective and preventive actions"
    page_subtitle = "Nonconformance management — ISO 15189 §8.7 / CAP"
    search_fields = ["reference", "title", "description"]
    filter_fields = {"status": "status", "category": "category"}
    columns = [
        ("Reference", "reference", "mono"), ("Title", "title", ""),
        ("Category", "get_category_display", ""), ("Severity", "severity", ""),
        ("Status", "status", ""), ("Raised", "raised_at", "nowrap"),
        ("Due", "due_date", "nowrap"),
    ]
    create_url_name = "compliance:capa_create"
    update_url_name = "compliance:capa_update"


class CapaCreateView(DxCreateView):
    model = CorrectiveAction
    form_class = compliance_forms.CorrectiveActionForm
    required_roles = LAB_STAFF
    page_title = "nonconformance"
    success_url = reverse_lazy("compliance:capa_list")

    def form_valid(self, form):
        form.instance.reference = next_capa_reference()
        form.instance.raised_by = self.request.user
        return super().form_valid(form)


class CapaUpdateView(DxUpdateView):
    model = CorrectiveAction
    form_class = compliance_forms.CorrectiveActionForm
    required_roles = LAB_STAFF
    page_title = "nonconformance"
    success_url = reverse_lazy("compliance:capa_list")

    def form_valid(self, form):
        if form.instance.status == CorrectiveAction.Status.CLOSED and not form.instance.closed_at:
            form.instance.closed_by = self.request.user
            form.instance.closed_at = timezone.now()
        return super().form_valid(form)


# ── Proficiency testing ──────────────────────────────────────────────────────


class ProficiencyListView(DxListView):
    model = ProficiencySurvey
    required_roles = LAB_STAFF
    page_title = "Proficiency testing"
    page_subtitle = "External quality assessment — CLIA 42 CFR §493.801"
    search_fields = ["provider", "survey_code", "discipline"]
    columns = [
        ("Provider", "provider", ""), ("Survey", "survey_code", "mono"),
        ("Year", "year", ""), ("Event", "event", ""), ("Discipline", "discipline", ""),
        ("Due", "due_date", "nowrap"), ("Submitted", "submitted_date", "nowrap"),
        ("Attested", "attestation_signed", ""),
    ]
    create_url_name = "compliance:pt_create"
    update_url_name = "compliance:pt_update"


class ProficiencyCreateView(DxCreateView):
    model = ProficiencySurvey
    form_class = compliance_forms.ProficiencySurveyForm
    required_roles = LAB_STAFF
    page_title = "proficiency survey"
    success_url = reverse_lazy("compliance:pt_list")


class ProficiencyUpdateView(DxUpdateView):
    model = ProficiencySurvey
    form_class = compliance_forms.ProficiencySurveyForm
    required_roles = LAB_STAFF
    page_title = "proficiency survey"
    success_url = reverse_lazy("compliance:pt_list")


class ProficiencyResultListView(DxListView):
    model = ProficiencyResult
    required_roles = LAB_STAFF
    page_title = "Proficiency results"
    search_fields = ["analyte", "sample_id"]
    columns = [
        ("Survey", "survey", ""), ("Analyte", "analyte", ""),
        ("Sample", "sample_id", "mono"), ("Reported", "reported_value", ""),
        ("Target", "target_value", ""), ("Z-score", "z_score", ""),
        ("Grade", "grade", ""), ("CAPA required", "requires_corrective_action", ""),
    ]
    create_url_name = "compliance:pt_result_create"


class ProficiencyResultCreateView(DxCreateView):
    model = ProficiencyResult
    form_class = compliance_forms.ProficiencyResultForm
    required_roles = LAB_STAFF
    page_title = "proficiency result"
    success_url = reverse_lazy("compliance:pt_result_list")


# ── Method validation ────────────────────────────────────────────────────────


class ValidationListView(DxListView):
    model = MethodValidation
    required_roles = MANAGERS
    page_title = "Method validation"
    page_subtitle = "Performance specification verification — CLIA 42 CFR §493.1253"
    search_fields = ["test__code", "test__name", "performed_by"]
    columns = [
        ("Test", "test.code", "mono"), ("Kind", "get_kind_display", ""),
        ("Instrument", "instrument.name", ""), ("Started", "started_on", "nowrap"),
        ("Completed", "completed_on", "nowrap"), ("All elements", "all_elements_verified", ""),
        ("Status", "status", ""),
    ]
    create_url_name = "compliance:validation_create"
    update_url_name = "compliance:validation_update"


class ValidationCreateView(DxCreateView):
    model = MethodValidation
    form_class = compliance_forms.MethodValidationForm
    required_roles = MANAGERS
    page_title = "method validation"
    success_url = reverse_lazy("compliance:validation_list")


class ValidationUpdateView(DxUpdateView):
    model = MethodValidation
    form_class = compliance_forms.MethodValidationForm
    required_roles = MANAGERS
    page_title = "method validation"
    success_url = reverse_lazy("compliance:validation_list")

    def form_valid(self, form):
        if form.instance.status == MethodValidation.Status.APPROVED and not form.instance.approved_at:
            form.instance.approved_by = self.request.user
            form.instance.approved_on = timezone.now()
        return super().form_valid(form)


# ── Risk register ────────────────────────────────────────────────────────────


class RiskListView(DxListView):
    model = RiskAssessment
    required_roles = MANAGERS
    page_title = "Risk register"
    page_subtitle = "Risk management — ISO 15189:2022 §8.5"
    search_fields = ["reference", "title", "process_area"]
    columns = [
        ("Reference", "reference", "mono"), ("Title", "title", ""),
        ("Process", "process_area", ""), ("Score", "risk_score", ""),
        ("Residual", "residual_score", ""), ("Rating", "rating", ""),
        ("Status", "status", ""), ("Next review", "next_review", "nowrap"),
    ]
    create_url_name = "compliance:risk_create"
    update_url_name = "compliance:risk_update"


class RiskCreateView(DxCreateView):
    model = RiskAssessment
    form_class = compliance_forms.RiskAssessmentForm
    required_roles = MANAGERS
    page_title = "risk"
    success_url = reverse_lazy("compliance:risk_list")

    def form_valid(self, form):
        year = timezone.localdate().year
        count = RiskAssessment.objects.filter(reference__startswith=f"RISK-{year}-").count()
        form.instance.reference = f"RISK-{year}-{count + 1:03d}"
        return super().form_valid(form)


class RiskUpdateView(DxUpdateView):
    model = RiskAssessment
    form_class = compliance_forms.RiskAssessmentForm
    required_roles = MANAGERS
    page_title = "risk"
    success_url = reverse_lazy("compliance:risk_list")


# ── Change control ───────────────────────────────────────────────────────────


class ChangeListView(DxListView):
    model = ChangeControl
    required_roles = MANAGERS
    page_title = "Change control"
    page_subtitle = "System and method changes — 21 CFR Part 11 §11.10(a)"
    search_fields = ["reference", "title", "description"]
    columns = [
        ("Reference", "reference", "mono"), ("Title", "title", ""),
        ("Type", "change_type", ""), ("Requested", "requested_at", "nowrap"),
        ("Status", "status", ""),
    ]
    create_url_name = "compliance:change_create"
    update_url_name = "compliance:change_update"


class ChangeCreateView(DxCreateView):
    model = ChangeControl
    form_class = compliance_forms.ChangeControlForm
    required_roles = MANAGERS
    page_title = "change request"
    success_url = reverse_lazy("compliance:change_list")

    def form_valid(self, form):
        year = timezone.localdate().year
        count = ChangeControl.objects.filter(reference__startswith=f"CHG-{year}-").count()
        form.instance.reference = f"CHG-{year}-{count + 1:03d}"
        form.instance.requested_by = self.request.user
        return super().form_valid(form)


class ChangeUpdateView(DxUpdateView):
    model = ChangeControl
    form_class = compliance_forms.ChangeControlForm
    required_roles = MANAGERS
    page_title = "change request"
    success_url = reverse_lazy("compliance:change_list")

    def form_valid(self, form):
        if form.instance.status == ChangeControl.Status.APPROVED and not form.instance.approved_at:
            form.instance.approved_by = self.request.user
            form.instance.approved_at = timezone.now()
        return super().form_valid(form)


# ── Training ─────────────────────────────────────────────────────────────────


class TrainingListView(DxListView):
    model = TrainingRecord
    required_roles = None
    page_title = "Training records"
    page_subtitle = "CLIA 42 CFR §493.1451(b)(8)"
    search_fields = ["user__name", "topic", "trainer"]
    columns = [
        ("Staff member", "user.name", ""), ("Topic", "topic", ""),
        ("Trainer", "trainer", ""), ("Completed", "completed_on", "nowrap"),
        ("Expires", "expires_on", "nowrap"), ("Status", "status", ""),
    ]
    create_url_name = "compliance:training_create"
    update_url_name = "compliance:training_update"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user")
        # Staff see their own record; managers see everyone's.
        if not self.request.user.is_manager:
            queryset = queryset.filter(user=self.request.user)
        return queryset


class TrainingCreateView(DxCreateView):
    model = TrainingRecord
    form_class = compliance_forms.TrainingRecordForm
    required_roles = MANAGERS
    page_title = "training record"
    success_url = reverse_lazy("compliance:training_list")


class TrainingUpdateView(DxUpdateView):
    model = TrainingRecord
    form_class = compliance_forms.TrainingRecordForm
    required_roles = MANAGERS
    page_title = "training record"
    success_url = reverse_lazy("compliance:training_list")


# ── Retention schedule ───────────────────────────────────────────────────────


class RetentionScheduleListView(DxListView):
    model = RetentionSchedule
    required_roles = MANAGERS
    page_title = "Record retention schedule"
    page_subtitle = "Minimum retention periods — CLIA 42 CFR §493.1105"
    columns = [
        ("Record class", "get_record_class_display", ""),
        ("Years", "retention_years", ""), ("Basis", "citation", "muted"),
        ("Destruction", "destruction_method", ""), ("Active", "active", ""),
    ]
    update_url_name = "compliance:retention_update"


class RetentionScheduleUpdateView(DxUpdateView):
    model = RetentionSchedule
    form_class = compliance_forms.RetentionScheduleForm
    required_roles = MANAGERS
    page_title = "retention rule"
    success_url = reverse_lazy("compliance:retention_schedule")


# ── HIPAA: PHI access and disclosure accounting ──────────────────────────────


class PHIAccessLogView(DxListView):
    model = PHIAccessLog
    required_roles = ADMIN_ONLY
    page_title = "PHI access log"
    page_subtitle = "Who viewed identifiable patient information — HIPAA §164.312(b)"
    search_fields = ["username", "patient_mrn", "path"]
    columns = [
        ("When", "timestamp", "nowrap"), ("User", "username", ""),
        ("Patient MRN", "patient_mrn", "mono"), ("Path", "path", "muted"),
        ("Purpose", "purpose", ""), ("Emergency override", "break_the_glass", ""),
        ("Address", "ip_address", "mono"),
    ]

    def get_queryset(self):
        return super().get_queryset().select_related("patient")


class DisclosureListView(DxListView):
    model = DisclosureAccounting
    required_roles = ADMIN_ONLY
    page_title = "Disclosure accounting"
    page_subtitle = (
        "Disclosures of protected health information — HIPAA §164.528. "
        "A patient may request an accounting covering the previous six years."
    )
    search_fields = ["recipient_name", "patient__mrn", "description"]
    columns = [
        ("When", "disclosed_at", "nowrap"), ("Patient", "patient.mrn", "mono"),
        ("Recipient", "recipient_name", ""), ("Purpose", "get_purpose_display", ""),
        ("Method", "method", ""), ("Authorised", "authorised_by_patient", ""),
        ("By", "disclosed_by", ""),
    ]

    def get_queryset(self):
        return super().get_queryset().select_related("patient")
