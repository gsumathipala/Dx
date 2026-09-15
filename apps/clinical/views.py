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
        "pending_count": CriticalValueNotification.objects.pending().count(),
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
        "overdue_count": EpidemiologyNotification.objects.overdue().count(),
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
