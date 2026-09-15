"""Patient reports, controlled documents and report distribution."""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES
from apps.common.views import DxCreateView, DxListView, DxUpdateView
from apps.reporting.models import (
    ControlledDocument, DistributionLog, DistributionRule, EmailQueueEntry, Requester,
)

LAB_STAFF = tuple(LAB_STAFF_ROLES)
MANAGERS = tuple(MANAGEMENT_ROLES)


class ControlledDocumentForm(forms.ModelForm):
    class Meta:
        model = ControlledDocument
        fields = [
            "title", "document_number", "category", "version", "status", "file",
            "effective_date", "review_due", "supersedes", "requires_acknowledgement",
            "department",
        ]
        widgets = {
            "effective_date": forms.DateInput(attrs={"type": "date"}),
            "review_due": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == ControlledDocument.Status.ACTIVE:
            if not cleaned.get("effective_date"):
                raise forms.ValidationError(
                    "An active controlled document must have an effective date."
                )
            if not cleaned.get("review_due"):
                raise forms.ValidationError(
                    "An active controlled document must have a scheduled review date "
                    "(ISO 15189 §8.3 requires periodic review)."
                )
        return cleaned


class RequesterForm(forms.ModelForm):
    class Meta:
        model = Requester
        fields = ["name", "type", "contact_name", "email", "phone", "fax",
                  "address", "delivery_preference", "notes", "active"]

    def clean(self):
        cleaned = super().clean()
        preference = cleaned.get("delivery_preference")
        if preference == Requester.Delivery.EMAIL and not cleaned.get("email"):
            raise forms.ValidationError("An email address is required for email delivery.")
        if preference == Requester.Delivery.FAX and not cleaned.get("fax"):
            raise forms.ValidationError("A fax number is required for fax delivery.")
        return cleaned


class DistributionRuleForm(forms.ModelForm):
    class Meta:
        model = DistributionRule
        fields = ["requester", "test", "method", "destination", "auto_release", "active"]


# ── Reports ──────────────────────────────────────────────────────────────────


@login_required
def reports(request):
    """Completed reports available for viewing and printing."""
    from apps.laboratory.models import Order

    orders = (
        Order.objects.filter(status="Completed")
        .select_related("patient")
        .prefetch_related("results", "signatures")
        .order_by("-completed_at")
    )
    query = (request.GET.get("q") or "").strip()
    if query:
        orders = orders.filter(
            Q(accession_number__icontains=query)
            | Q(patient__mrn__icontains=query)
            | Q(patient__last_name__icontains=query)
        )

    paginator = Paginator(orders, 40)
    return render(request, "reporting/reports.html", {
        "page_obj": paginator.get_page(request.GET.get("page")),
        "query": query,
        "querystring": f"q={query}&" if query else "",
    })


@login_required
def report_detail(request, pk):
    """The printable patient report, with its electronic signature manifest."""
    from apps.compliance.models import ElectronicSignature
    from apps.laboratory.models import Order, Result

    order = get_object_or_404(
        Order.objects.select_related("patient").prefetch_related("results__test", "signatures"),
        pk=pk,
    )

    analytes = [r for r in order.results.all() if not r.is_report_row]
    narrative = next((r for r in order.results.all() if r.is_report_row), None)

    return render(request, "reporting/report_detail.html", {
        "order": order,
        "patient": order.patient,
        "results": analytes,
        "narrative": narrative,
        "signatures": ElectronicSignature.objects.filter(
            entity_type="laboratory.Order", entity_id=str(order.pk)
        ).order_by("signed_at"),
        "legacy_signatures": order.signatures.all(),
        "amendments": order.amendments.all(),
        "printed_at": timezone.now(),
    })


@login_required
def cumulative_report(request):
    """Trended results for one patient across multiple episodes."""
    from apps.laboratory.models import Result
    from apps.patients.models import Patient

    patient_id = request.GET.get("patient")
    patient = Patient.objects.filter(pk=patient_id).first() if patient_id else None

    grid, dates = {}, []
    if patient:
        results = (
            Result.objects.filter(order__patient=patient)
            .exclude(test__isnull=True)
            .select_related("test", "order")
            .order_by("order__timestamp")
        )
        for result in results:
            stamp = result.order.timestamp
            if stamp not in dates:
                dates.append(stamp)
            grid.setdefault(result.test, {})[stamp] = result

    return render(request, "reporting/cumulative.html", {
        "patients": Patient.objects.order_by("last_name")[:500],
        "patient": patient,
        "grid": grid,
        "dates": dates,
    })


@login_required
def email_delivery(request):
    """Outbound report delivery queue."""
    if not request.user.is_manager:
        messages.error(request, "Your role does not permit access to report delivery.")
        return redirect("operations:dashboard")

    return render(request, "reporting/email_delivery.html", {
        "queue": EmailQueueEntry.objects.select_related("order").order_by("-created_at")[:100],
        "pending": EmailQueueEntry.objects.filter(status=EmailQueueEntry.Status.PENDING).count(),
        "failed": EmailQueueEntry.objects.filter(status=EmailQueueEntry.Status.FAILED).count(),
        "logs": DistributionLog.objects.select_related("order").order_by("-sent_at")[:50],
    })


# ── Controlled documents ─────────────────────────────────────────────────────


# ── Requesters and distribution ──────────────────────────────────────────────


@login_required
def amend_report_view(request, pk):
    """Issue a corrected report for an already-released order (CAP)."""
    from apps.compliance.forms import AmendedReportForm
    from apps.compliance.services import ControlViolation
    from apps.laboratory.models import Order
    from apps.laboratory.services import amend_report

    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit amending a report.")
        return redirect("reporting:reports")

    order = get_object_or_404(
        Order.objects.select_related("patient").prefetch_related("results__test"), pk=pk
    )
    if not order.is_complete:
        messages.error(
            request,
            "Only a released report can be amended. Correct the result in the "
            "usual way before it is verified.",
        )
        return redirect("laboratory:result_entry", pk=order.pk)

    form = AmendedReportForm(request.POST or None, order=order)
    if request.method == "POST" and form.is_valid():
        try:
            amendment = amend_report(
                order=order,
                result=form.cleaned_data["result"],
                corrected_value=form.cleaned_data["corrected_value"],
                reason=form.cleaned_data["reason"],
                narrative=form.cleaned_data["narrative"],
                user=request.user,
                password=form.cleaned_data["password"],
                request=request,
                notified_method=form.cleaned_data.get("notification_method") or None,
            )
        except ControlViolation as violation:
            messages.error(request, str(violation))
        else:
            messages.success(
                request,
                f"Amended report v{amendment.version} issued. "
                f"Nonconformance {amendment.corrective_action.reference} was opened.",
            )
            return redirect("reporting:report_detail", pk=order.pk)

    return render(request, "reporting/amend.html", {
        "order": order,
        "form": form,
        "results": order.results.exclude(test_key="REPORT").select_related("test"),
        "amendments": order.amendments.all(),
    })


@login_required
def acknowledge_document(request, pk):
    """Record that the signed-in user has read the current version."""
    from apps.compliance.models import DocumentAcknowledgement

    document = get_object_or_404(ControlledDocument, pk=pk)
    if request.method == "POST":
        _, created = DocumentAcknowledgement.objects.get_or_create(
            document=document, document_version=document.version, user=request.user
        )
        messages.success(
            request,
            "Acknowledgement recorded." if created else "You had already acknowledged this version.",
        )
    return redirect("reporting:document_list")


def stamp_document_approval(view, form):
    """Record who approved a document the moment it becomes active.

    Passed to the ``documents`` CrudResource as its update hook.
    """
    if form.instance.status == ControlledDocument.Status.ACTIVE and not form.instance.approved_at:
        form.instance.approved_by = view.request.user
        form.instance.approved_at = timezone.now()
