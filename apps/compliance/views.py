"""Regulatory compliance screens."""
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from apps.common.constants import (
    LAB_STAFF_ROLES, MANAGEMENT_ROLES, SYSTEM_ROLES, Role,
)
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
#: Change control covers software and configuration changes, which the
#: installer performs and must therefore be able to record.
MANAGERS_AND_INSTALLER = tuple(dict.fromkeys(MANAGERS + tuple(SYSTEM_ROLES)))


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
    """A single view of every outstanding regulatory obligation.

    Every count here is answered by the database. These figures were previously
    computed by loading whole tables and counting in Python, which is fine at a
    dozen rows and not at a year's worth.
    """
    from apps.accounts.models import UserCompetency
    from apps.audit.models import AuditEvent
    from apps.audit.verification import latest_checkpoint, open_alerts
    from apps.clinical.models import CriticalValueNotification, EpidemiologyNotification
    from apps.quality.models import Equipment, QcRun
    from apps.reporting.models import ControlledDocument

    today = timezone.localdate()
    soon = today + timedelta(days=30)

    context = {
        "capa_open": CorrectiveAction.objects.open().count(),
        "capa_overdue": CorrectiveAction.objects.overdue().count(),
        "pt_overdue": ProficiencySurvey.objects.overdue().count(),
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
        "documents_review_overdue": ControlledDocument.objects.review_overdue()[:10],
        "calibration_overdue": Equipment.objects.calibration_overdue()[:10],
        "qc_failures": QcRun.objects.filter(
            status=QcRun.Status.FAIL, timestamp__gte=timezone.now() - timedelta(days=7),
            corrective_action__isnull=True,
        ).select_related("definition")[:10],
        "critical_outstanding": CriticalValueNotification.objects.pending().count(),
        "critical_overdue": CriticalValueNotification.objects.overdue().count(),
        "epi_overdue": EpidemiologyNotification.objects.overdue().count(),
        "risks_high": RiskAssessment.objects.high_rated()[:10],
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


# ── Proficiency testing ──────────────────────────────────────────────────────


# ── Method validation ────────────────────────────────────────────────────────


# ── Risk register ────────────────────────────────────────────────────────────


# ── Change control ───────────────────────────────────────────────────────────


# ── Training ─────────────────────────────────────────────────────────────────


# ── Retention schedule ───────────────────────────────────────────────────────


# ── HIPAA: PHI access and disclosure accounting ──────────────────────────────


# ── Save hooks for the declarative CRUD resources in urls.py ─────────────────


def stamp_capa_creation(view, form):
    form.instance.reference = next_capa_reference()
    form.instance.raised_by = view.request.user


def stamp_capa_closure(view, form):
    if form.instance.status == CorrectiveAction.Status.CLOSED and not form.instance.closed_at:
        form.instance.closed_by = view.request.user
        form.instance.closed_at = timezone.now()


def stamp_validation_approval(view, form):
    if form.instance.status == MethodValidation.Status.APPROVED and not form.instance.approved_on:
        form.instance.approved_by = view.request.user
        form.instance.approved_on = timezone.now()


def stamp_risk_reference(view, form):
    year = timezone.localdate().year
    count = RiskAssessment.objects.filter(reference__startswith=f"RISK-{year}-").count()
    form.instance.reference = f"RISK-{year}-{count + 1:03d}"


def stamp_change_reference(view, form):
    year = timezone.localdate().year
    count = ChangeControl.objects.filter(reference__startswith=f"CHG-{year}-").count()
    form.instance.reference = f"CHG-{year}-{count + 1:03d}"
    form.instance.requested_by = view.request.user


def stamp_change_approval(view, form):
    if form.instance.status == ChangeControl.Status.APPROVED and not form.instance.approved_at:
        form.instance.approved_by = view.request.user
        form.instance.approved_at = timezone.now()
