"""Accessioning, result entry, validation and specimen reception."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from apps.common.constants import AuditAction, LAB_STAFF_ROLES, MANAGEMENT_ROLES, OrderStatus, Role
from apps.common.views import DxCreateView, DxListView, DxUpdateView
from apps.compliance.services import ControlViolation
from apps.laboratory import forms as lab_forms
from apps.laboratory.models import (
    AuthorizationQueue, Order, PhlebotomySchedule, Result, RetentionPolicy,
    Specimen, SpecimenReceiving, TestDefinition,
)
from apps.laboratory.services import ResultEntryError, create_order, save_results

LAB_STAFF = tuple(LAB_STAFF_ROLES)
MANAGERS = tuple(MANAGEMENT_ROLES)
ACCESSIONING_ROLES = LAB_STAFF + (Role.CLERK,)


# ── Accessioning ─────────────────────────────────────────────────────────────


@login_required
def accessioning(request):
    """Register a new test request and allocate its accession number."""
    if request.user.role not in ACCESSIONING_ROLES:
        messages.error(request, "Your role does not permit accessioning.")
        return redirect("operations:dashboard")

    form = lab_forms.AccessionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        order = create_order(
            patient=form.cleaned_data["patient"],
            tests=form.cleaned_data["tests"],
            ordered_by=form.cleaned_data["ordered_by"],
            priority=form.cleaned_data["priority"],
            requester=form.cleaned_data["requester"],
            specimen_type=form.cleaned_data["specimen_type"] or None,
            user=request.user,
        )
        messages.success(request, f"Accessioned as {order.accession_number}.")
        return redirect("laboratory:accessioning")

    recent = (
        Order.objects.select_related("patient")
        .prefetch_related("tests")
        .order_by("-timestamp")[:15]
    )
    return render(request, "laboratory/accessioning.html", {"form": form, "recent": recent})


# ── Worklist and result entry ────────────────────────────────────────────────


@login_required
def results_worklist(request):
    """Orders awaiting result entry or authorisation."""
    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit result entry.")
        return redirect("operations:dashboard")

    orders = (
        Order.objects.select_related("patient", "queue")
        .prefetch_related("tests", "results")
        .exclude(status__in=[OrderStatus.COMPLETED, OrderStatus.CANCELLED, OrderStatus.REJECTED])
        .order_by("priority", "timestamp")
    )

    query = (request.GET.get("q") or "").strip()
    if query:
        orders = orders.filter(
            Q(accession_number__icontains=query)
            | Q(patient__mrn__icontains=query)
            | Q(patient__last_name__icontains=query)
        )

    status = request.GET.get("status")
    if status:
        orders = orders.filter(status=status)

    paginator = Paginator(orders, 40)
    return render(request, "laboratory/results_worklist.html", {
        "page_obj": paginator.get_page(request.GET.get("page")),
        "statuses": OrderStatus.choices,
        "filters": request.GET,
        "querystring": "",
    })


@login_required
def result_entry(request, pk):
    """Enter, technically validate or clinically verify results for one order."""
    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit result entry.")
        return redirect("operations:dashboard")

    order = get_object_or_404(
        Order.objects.select_related("patient").prefetch_related("tests", "results"), pk=pk
    )
    form = lab_forms.ResultEntryForm(request.POST or None, order=order)

    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action") or None
        try:
            outcome = save_results(
                order=order,
                values=form.values(),
                user=request.user,
                action=action,
                notes=form.cleaned_data.get("notes") or None,
                queue=form.cleaned_data.get("queue"),
                password=form.cleaned_data.get("password") or None,
                request=request,
                reason=form.cleaned_data.get("reason") or None,
            )
        except ControlViolation as violation:
            messages.error(request, str(violation))
        except ResultEntryError as error:
            messages.error(request, str(error))
        else:
            _report_engine_outcome(request, outcome)
            messages.success(request, f"Results saved for {order.accession_number}.")
            return redirect("laboratory:results")

    from apps.audit.models import AuditEvent

    return render(request, "laboratory/result_entry.html", {
        "order": order,
        "form": form,
        "existing": {r.test_key: r for r in order.results.all()},
        "signatures": order.signatures.all(),
        "delta_flags": order.delta_flags.select_related("test", "rule"),
        "critical_values": order.critical_values.all(),
        "audit_events": AuditEvent.objects.for_entity("laboratory.Order", order.pk)[:10],
        "entity_type": "laboratory.Order",
    })


def _report_engine_outcome(request, outcome: dict) -> None:
    """Surface what the clinical rules did, instead of burying it in a log."""
    for code, result in (outcome.get("engine") or {}).items():
        if result.get("critical"):
            messages.warning(
                request,
                f"{code}: critical value detected — clinician notification is required "
                "and must be documented.",
            )
        if result.get("delta_flags"):
            messages.info(request, f"{code}: delta check flagged a significant change from the previous result.")
        for test in result.get("reflex_added") or []:
            messages.info(request, f"{code}: reflex rule added {test.code} to this order.")
        for notification in result.get("notifiable") or []:
            messages.warning(
                request,
                f"{code}: notifiable condition '{notification.condition.name}' detected — "
                f"report to {notification.condition.reporting_body} within {notification.condition.timeframe}.",
            )
        for error in result.get("errors") or []:
            messages.error(request, f"{code}: clinical rule error — {error}")


# ── Specimen reception ───────────────────────────────────────────────────────


@login_required
def receiving(request):
    """Record specimen arrival and condition."""
    if request.user.role not in ACCESSIONING_ROLES:
        messages.error(request, "Your role does not permit specimen reception.")
        return redirect("operations:dashboard")

    form = lab_forms.SpecimenReceivingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        receipt = form.save(commit=False)
        receipt.received_by = request.user.username
        receipt.save()

        order = receipt.order
        if receipt.status == SpecimenReceiving.Status.REJECTED:
            order.status = OrderStatus.REJECTED
            messages.warning(
                request,
                f"{order.accession_number} rejected — the requester must be told recollection is needed.",
            )
        else:
            order.status = OrderStatus.RECEIVED
            messages.success(request, f"{order.accession_number} received.")
        order.updated_at = timezone.now()
        order.save(update_fields=["status", "updated_at"])
        return redirect("laboratory:receiving")

    return render(request, "laboratory/receiving.html", {
        "form": form,
        "recent": SpecimenReceiving.objects.select_related("order", "specimen").order_by("-received_at")[:20],
        "awaiting": Order.objects.filter(status=OrderStatus.PENDING).select_related("patient")[:20],
    })


# ── Phlebotomy ───────────────────────────────────────────────────────────────


class PhlebotomyListView(DxListView):
    model = PhlebotomySchedule
    required_roles = ACCESSIONING_ROLES + (Role.PHLEBOTOMIST,)
    page_title = "Phlebotomy rounds"
    search_fields = ["patient__mrn", "patient__last_name", "ward_location"]
    filter_fields = {"status": "status"}
    columns = [
        ("Scheduled", "scheduled_at", "nowrap"), ("Patient", "patient.full_name", ""),
        ("MRN", "patient.mrn", "mono"), ("Ward", "ward_location", ""),
        ("Type", "collection_type", ""), ("Assigned", "assigned_to.name", ""),
        ("Status", "status", ""),
    ]
    create_url_name = "laboratory:phlebotomy_create"
    update_url_name = "laboratory:phlebotomy_update"

    def get_queryset(self):
        return super().get_queryset().select_related("patient", "assigned_to")


class PhlebotomyCreateView(DxCreateView):
    model = PhlebotomySchedule
    form_class = lab_forms.PhlebotomyForm
    required_roles = ACCESSIONING_ROLES
    page_title = "phlebotomy round"
    success_url = reverse_lazy("laboratory:phlebotomy")


class PhlebotomyUpdateView(DxUpdateView):
    model = PhlebotomySchedule
    form_class = lab_forms.PhlebotomyForm
    required_roles = ACCESSIONING_ROLES + (Role.PHLEBOTOMIST,)
    page_title = "phlebotomy round"
    success_url = reverse_lazy("laboratory:phlebotomy")


# ── Configuration: tests, queues, retention ──────────────────────────────────


class TestListView(DxListView):
    model = TestDefinition
    required_roles = MANAGERS
    page_title = "Test definitions"
    page_subtitle = "The test catalogue, its units, reference intervals and critical limits."
    search_fields = ["code", "name", "loinc_code"]
    columns = [
        ("Code", "code", "mono"), ("Name", "name", ""),
        ("Department", "department.name", ""), ("Units", "units", ""),
        ("Reference", "reference_display", "nowrap"), ("TAT (h)", "tat_hours", ""),
        ("LOINC", "loinc_code", "mono"), ("Active", "active", ""),
    ]
    create_url_name = "laboratory:test_create"
    update_url_name = "laboratory:test_update"

    def get_queryset(self):
        return super().get_queryset().select_related("department")


class TestCreateView(DxCreateView):
    model = TestDefinition
    form_class = lab_forms.TestDefinitionForm
    required_roles = MANAGERS
    page_title = "test definition"
    success_url = reverse_lazy("laboratory:test_list")


class TestUpdateView(DxUpdateView):
    model = TestDefinition
    form_class = lab_forms.TestDefinitionForm
    required_roles = MANAGERS
    page_title = "test definition"
    success_url = reverse_lazy("laboratory:test_list")


class QueueListView(DxListView):
    model = AuthorizationQueue
    required_roles = MANAGERS
    page_title = "Authorisation queues"
    search_fields = ["name", "description"]
    columns = [
        ("Name", "name", ""), ("Department", "department.name", ""),
        ("Allowed roles", "allowed_roles", ""), ("Created", "created_at", "nowrap"),
    ]
    create_url_name = "laboratory:queue_create"
    update_url_name = "laboratory:queue_update"


class QueueCreateView(DxCreateView):
    model = AuthorizationQueue
    form_class = lab_forms.QueueForm
    required_roles = MANAGERS
    page_title = "queue"
    success_url = reverse_lazy("laboratory:queue_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user.username
        return super().form_valid(form)


class QueueUpdateView(DxUpdateView):
    model = AuthorizationQueue
    form_class = lab_forms.QueueForm
    required_roles = MANAGERS
    page_title = "queue"
    success_url = reverse_lazy("laboratory:queue_list")


class RetentionListView(DxListView):
    model = RetentionPolicy
    required_roles = MANAGERS
    page_title = "Sample retention policies"
    page_subtitle = "How long each specimen type is kept before disposal."
    search_fields = ["specimen_type"]
    columns = [
        ("Specimen type", "specimen_type", ""), ("Days", "retention_days", ""),
        ("Storage", "temperature", ""), ("Disposal", "disposal_method", ""),
        ("Active", "active", ""),
    ]
    create_url_name = "laboratory:retention_create"
    update_url_name = "laboratory:retention_update"


class RetentionCreateView(DxCreateView):
    model = RetentionPolicy
    form_class = lab_forms.RetentionPolicyForm
    required_roles = MANAGERS
    page_title = "retention policy"
    success_url = reverse_lazy("laboratory:retention_list")


class RetentionUpdateView(DxUpdateView):
    model = RetentionPolicy
    form_class = lab_forms.RetentionPolicyForm
    required_roles = MANAGERS
    page_title = "retention policy"
    success_url = reverse_lazy("laboratory:retention_list")
