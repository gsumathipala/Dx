"""Clinical engine configuration, critical values and epidemiology."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from apps.clinical import forms as clinical_forms
from apps.clinical.models import (
    CalculatedTest, CriticalValueNotification, DeltaCheckFlag, DeltaCheckRule,
    DemographicReferenceRange, EpidemiologyNotification, NotifiableCondition, ReflexRule,
)
from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES, Role
from apps.common.views import DxCreateView, DxDeleteView, DxListView, DxUpdateView

LAB_STAFF = tuple(LAB_STAFF_ROLES)
MANAGERS = tuple(MANAGEMENT_ROLES)
ADMIN_ONLY = (Role.ADMIN,)


# ── Critical values ──────────────────────────────────────────────────────────


@login_required
def critical_values(request):
    """Outstanding critical results awaiting clinician notification."""
    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit access to critical values.")
        return redirect("operations:dashboard")

    notifications = (
        CriticalValueNotification.objects.select_related("patient", "test", "order")
        .order_by("status", "created_at")
    )
    status = request.GET.get("status") or CriticalValueNotification.Status.PENDING
    if status != "all":
        notifications = notifications.filter(status=status)

    return render(request, "clinical/critical_values.html", {
        "notifications": notifications[:100],
        "statuses": CriticalValueNotification.Status.choices,
        "selected_status": status,
        "pending_count": CriticalValueNotification.objects.filter(
            status=CriticalValueNotification.Status.PENDING
        ).count(),
    })


@login_required
def acknowledge_critical(request, pk):
    """Record the read-back that closes a critical value notification."""
    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit this action.")
        return redirect("operations:dashboard")

    notification = get_object_or_404(
        CriticalValueNotification.objects.select_related("patient", "test", "order"), pk=pk
    )
    form = clinical_forms.CriticalAcknowledgementForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        acknowledgement = form.save(commit=False)
        acknowledgement.notification = notification
        acknowledgement.acknowledged_by = request.user.username
        acknowledgement.save()

        notification.status = (
            CriticalValueNotification.Status.ESCALATED
            if acknowledgement.escalated_to
            else CriticalValueNotification.Status.ACKNOWLEDGED
        )
        notification.save(update_fields=["status"])
        messages.success(request, "Critical value notification documented.")
        return redirect("clinical:critical_values")

    return render(request, "clinical/acknowledge_critical.html", {
        "notification": notification,
        "form": form,
    })


# ── Delta check flags ────────────────────────────────────────────────────────


class DeltaFlagListView(DxListView):
    model = DeltaCheckFlag
    required_roles = LAB_STAFF
    page_title = "Delta check flags"
    page_subtitle = "Results that changed significantly from the patient's previous value."
    columns = [
        ("Flagged", "flagged_at", "nowrap"), ("Order", "order.accession_number", "mono"),
        ("Test", "test.code", "mono"), ("Previous", "previous_value", ""),
        ("Current", "current_value", ""), ("Change %", "delta_percent", ""),
        ("Acknowledged", "is_acknowledged", ""),
    ]

    def get_queryset(self):
        return super().get_queryset().select_related("order", "test", "rule")


# ── Epidemiology ─────────────────────────────────────────────────────────────


@login_required
def epidemiology(request):
    """Notifiable conditions detected and their reporting status."""
    if not request.user.is_manager:
        messages.error(request, "Your role does not permit access to epidemiology reporting.")
        return redirect("operations:dashboard")

    notifications = (
        EpidemiologyNotification.objects.select_related("patient", "condition", "order")
        .order_by("status", "detected_at")
    )
    return render(request, "clinical/epidemiology.html", {
        "notifications": notifications[:200],
        "overdue": [n for n in notifications if n.is_overdue],
    })


@login_required
def submit_epidemiology(request, pk):
    """Mark a notifiable condition as reported to the authority."""
    if not request.user.is_manager:
        messages.error(request, "Your role does not permit this action.")
        return redirect("operations:dashboard")

    notification = get_object_or_404(EpidemiologyNotification, pk=pk)
    if request.method == "POST":
        notification.status = EpidemiologyNotification.Status.SUBMITTED
        notification.submitted_by = request.user.username
        notification.submitted_at = timezone.now()
        notification.reference_number = request.POST.get("reference_number") or None
        notification.notes = request.POST.get("notes") or notification.notes
        notification.save()
        messages.success(request, f"{notification.condition.name} recorded as reported.")
    return redirect("clinical:epidemiology")


# ── Rule configuration ───────────────────────────────────────────────────────


class DeltaRuleListView(DxListView):
    model = DeltaCheckRule
    required_roles = MANAGERS
    page_title = "Delta check rules"
    search_fields = ["test_code", "test__name"]
    columns = [
        ("Test", "test_code", "mono"), ("Type", "get_delta_type_display", ""),
        ("Threshold", "threshold", ""), ("Direction", "direction", ""),
        ("Lookback (days)", "lookback_days", ""), ("Enabled", "enabled", ""),
    ]
    create_url_name = "clinical:delta_rule_create"
    update_url_name = "clinical:delta_rule_update"


class DeltaRuleCreateView(DxCreateView):
    model = DeltaCheckRule
    form_class = clinical_forms.DeltaCheckRuleForm
    required_roles = MANAGERS
    page_title = "delta check rule"
    success_url = reverse_lazy("clinical:delta_rules")

    def form_valid(self, form):
        form.instance.created_by = self.request.user.username
        return super().form_valid(form)


class DeltaRuleUpdateView(DxUpdateView):
    model = DeltaCheckRule
    form_class = clinical_forms.DeltaCheckRuleForm
    required_roles = MANAGERS
    page_title = "delta check rule"
    success_url = reverse_lazy("clinical:delta_rules")


class ReflexRuleListView(DxListView):
    model = ReflexRule
    required_roles = MANAGERS
    page_title = "Reflex testing rules"
    search_fields = ["name", "add_test_code"]
    columns = [
        ("Name", "name", ""), ("Trigger", "trigger_test.code", "mono"),
        ("Condition", "operator", ""), ("Threshold", "threshold", ""),
        ("Adds", "add_test_code", "mono"), ("Enabled", "enabled", ""),
    ]
    create_url_name = "clinical:reflex_rule_create"
    update_url_name = "clinical:reflex_rule_update"


class ReflexRuleCreateView(DxCreateView):
    model = ReflexRule
    form_class = clinical_forms.ReflexRuleForm
    required_roles = MANAGERS
    page_title = "reflex rule"
    success_url = reverse_lazy("clinical:reflex_rules")

    def form_valid(self, form):
        form.instance.created_by = self.request.user.username
        return super().form_valid(form)


class ReflexRuleUpdateView(DxUpdateView):
    model = ReflexRule
    form_class = clinical_forms.ReflexRuleForm
    required_roles = MANAGERS
    page_title = "reflex rule"
    success_url = reverse_lazy("clinical:reflex_rules")


class DemographicRangeListView(DxListView):
    model = DemographicReferenceRange
    required_roles = MANAGERS
    page_title = "Demographic reference intervals"
    page_subtitle = "Age, sex and pregnancy specific intervals, applied in preference to the test default."
    search_fields = ["test_code"]
    columns = [
        ("Test", "test_code", "mono"), ("Age from", "age_min", ""), ("Age to", "age_max", ""),
        ("Sex", "gender", ""), ("Pregnancy", "pregnancy", ""),
        ("Normal low", "low_normal", ""), ("Normal high", "high_normal", ""),
        ("Critical low", "low_critical", ""), ("Critical high", "high_critical", ""),
        ("Active", "active", ""),
    ]
    create_url_name = "clinical:demographic_range_create"
    update_url_name = "clinical:demographic_range_update"


class DemographicRangeCreateView(DxCreateView):
    model = DemographicReferenceRange
    form_class = clinical_forms.DemographicRangeForm
    required_roles = MANAGERS
    page_title = "reference interval"
    success_url = reverse_lazy("clinical:demographic_ranges")


class DemographicRangeUpdateView(DxUpdateView):
    model = DemographicReferenceRange
    form_class = clinical_forms.DemographicRangeForm
    required_roles = MANAGERS
    page_title = "reference interval"
    success_url = reverse_lazy("clinical:demographic_ranges")


class CalculatedTestListView(DxListView):
    model = CalculatedTest
    required_roles = MANAGERS
    page_title = "Calculated tests"
    page_subtitle = "Derived analytes computed from other results rather than measured."
    search_fields = ["test_code", "name"]
    columns = [
        ("Code", "test_code", "mono"), ("Name", "name", ""),
        ("Formula", "get_formula_display", ""), ("Inputs", "inputs", ""),
        ("Unit", "unit", ""), ("Active", "active", ""),
    ]
    create_url_name = "clinical:calculated_test_create"
    update_url_name = "clinical:calculated_test_update"


class CalculatedTestCreateView(DxCreateView):
    model = CalculatedTest
    form_class = clinical_forms.CalculatedTestForm
    required_roles = MANAGERS
    page_title = "calculated test"
    success_url = reverse_lazy("clinical:calculated_tests")


class CalculatedTestUpdateView(DxUpdateView):
    model = CalculatedTest
    form_class = clinical_forms.CalculatedTestForm
    required_roles = MANAGERS
    page_title = "calculated test"
    success_url = reverse_lazy("clinical:calculated_tests")


class NotifiableConditionListView(DxListView):
    model = NotifiableCondition
    required_roles = ADMIN_ONLY
    page_title = "Notifiable conditions"
    page_subtitle = "Conditions that must be reported to public health authorities."
    search_fields = ["name", "organism", "reporting_body"]
    columns = [
        ("Condition", "name", ""), ("Organism", "organism", ""),
        ("Reporting body", "reporting_body", ""), ("Timeframe", "timeframe", ""),
        ("Active", "active", ""),
    ]
    create_url_name = "clinical:notifiable_create"
    update_url_name = "clinical:notifiable_update"


class NotifiableConditionCreateView(DxCreateView):
    model = NotifiableCondition
    form_class = clinical_forms.NotifiableConditionForm
    required_roles = ADMIN_ONLY
    page_title = "notifiable condition"
    success_url = reverse_lazy("clinical:notifiable_list")


class NotifiableConditionUpdateView(DxUpdateView):
    model = NotifiableCondition
    form_class = clinical_forms.NotifiableConditionForm
    required_roles = ADMIN_ONLY
    page_title = "notifiable condition"
    success_url = reverse_lazy("clinical:notifiable_list")
