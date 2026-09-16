"""Accessioning, result entry, validation and specimen reception."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from apps.accounts import locking
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
    page = paginator.get_page(request.GET.get("page"))

    # An order is offerable for batch verification when it has been technically
    # validated by somebody other than the person looking at it. The server
    # re-checks every gate on submission regardless.
    verifiable = set()
    for order in page:
        if order.status != OrderStatus.TECHNICALLY_VALIDATED:
            continue
        if request.user.username in {r.entered_by for r in order.results.all()}:
            continue
        verifiable.add(order.pk)

    return render(request, "laboratory/results_worklist.html", {
        "page_obj": page,
        "statuses": OrderStatus.choices,
        "filters": request.GET,
        "querystring": "",
        "verifiable": verifiable,
        "verifiable_count": len(verifiable),
    })


@login_required
def verify_batch_view(request):
    """Clinically verify a selection of orders from the worklist."""
    from apps.laboratory.services import verify_batch

    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit verification.")
        return redirect("operations:dashboard")

    order_ids = request.POST.getlist("orders")
    password = request.POST.get("password") or ""

    if not order_ids:
        messages.error(request, "Select at least one order to verify.")
        return redirect("laboratory:results")
    if not password:
        messages.error(request, "Your password is required to apply an electronic signature.")
        return redirect("laboratory:results")

    orders = (
        Order.objects.filter(pk__in=order_ids)
        .select_related("patient")
        .prefetch_related("results", "tests")
    )
    verified, refusals = verify_batch(
        orders=list(orders), user=request.user, password=password,
        request=request, reason=request.POST.get("reason") or None,
    )

    if verified:
        messages.success(
            request,
            f"Verified and released {len(verified)} order"
            f"{'' if len(verified) == 1 else 's'}.",
        )
    for order, reason in refusals:
        messages.error(request, f"{order.accession_number}: {reason}")

    return redirect("laboratory:results")


@login_required
def result_entry(request, pk):
    """Enter, technically validate or clinically verify results for one order."""
    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit result entry.")
        return redirect("operations:dashboard")

    order = get_object_or_404(
        Order.objects.select_related("patient").prefetch_related("tests", "results"), pk=pk
    )

    # Take the lock before building the form. Two scientists entering results
    # on one order is not a merge conflict — it is one of them silently
    # overwriting the other, on a record a clinician will act on.
    lock = locking.acquire("laboratory.Order", order.pk, request.user)
    form = lab_forms.ResultEntryForm(request.POST or None, order=order)

    if request.method == "POST" and not lock.editable:
        # Refused rather than merged. The other user's work is not ours to
        # reconcile, and a partially-applied save is worse than none.
        messages.error(request, lock.message)
        return redirect("laboratory:result_entry", pk=order.pk)

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
            # The work is done; do not hold the record while walking away.
            locking.release("laboratory.Order", order.pk, request.user)
            return redirect("laboratory:results")

    from apps.audit.models import AuditEvent

    return render(request, "laboratory/result_entry.html", {
        "order": order,
        "form": form,
        "rows": _entry_rows(order, form),
        "next_action": _next_action(order, request.user),
        "signatures": order.signatures.all(),
        "delta_flags": order.delta_flags.select_related("test", "rule"),
        "critical_values": order.critical_values.all(),
        "audit_events": AuditEvent.objects.for_entity("laboratory.Order", order.pk)[:10],
        "entity_type": "laboratory.Order",
        "lock": lock,
        "lock_entity_type": "laboratory.Order",
        "lock_entity_id": str(order.pk),
    })


def _entry_rows(order, form):
    """One row per test, carrying the patient's previous value for that test.

    Whether 131 mmol/L is plausible depends on what it was last time. That
    comparison used to live on a different screen; the delta-check engine
    already fetches it, so it costs one extra query for the whole order rather
    than one per test.
    """
    from apps.laboratory.models import Result

    existing = {r.test_key: r for r in order.results.all()}

    previous_by_test = {}
    earlier = (
        Result.objects.filter(
            order__patient_id=order.patient_id,
            numeric_value__isnull=False,
            order__timestamp__lt=order.timestamp,
        )
        .exclude(order_id=order.pk)
        .select_related("order", "test")
        .order_by("test_key", "-order__timestamp")
    )
    for result in earlier:
        previous_by_test.setdefault(result.test_key, result)

    rows = []
    for test, field in form.result_fields:
        current = existing.get(test.id)
        previous = previous_by_test.get(test.id)
        direction = ""
        if previous is not None and current is not None and current.numeric_value is not None:
            if current.numeric_value > previous.numeric_value:
                direction = "up"
            elif current.numeric_value < previous.numeric_value:
                direction = "down"
        rows.append({
            "test": test,
            "field": field,
            "result": current,
            "previous": previous,
            "direction": direction,
        })
    return rows


def _next_action(order, user):
    """The single action this order is ready for, given who is looking at it.

    Offering all three buttons on every visit meant two of them were usually
    refused. The order's state already determines which one applies.
    """
    from apps.common.constants import AuditAction

    if order.status in {OrderStatus.PENDING, OrderStatus.RECEIVED,
                        OrderStatus.IN_PROGRESS, OrderStatus.RESULTED}:
        if order.results.exists() and order.status == OrderStatus.RESULTED:
            return {"value": AuditAction.TECHNICAL_VALIDATE,
                    "label": "Technically validate",
                    "needs_password": True,
                    "hint": "Confirms the analytical run is sound."}
        return {"value": "", "label": "Save results", "needs_password": False,
                "hint": "Records the values without authorising them."}

    if order.status == OrderStatus.TECHNICALLY_VALIDATED:
        entered_by = {r.entered_by for r in order.results.all()}
        if user.username in entered_by:
            return {"value": None, "label": "", "needs_password": False,
                    "hint": "You entered these results, so a second qualified "
                            "person must verify them."}
        return {"value": AuditAction.CLINICAL_VERIFY,
                "label": "Clinically verify and release",
                "needs_password": True,
                "hint": "Completes the order and releases the report."}

    return {"value": None, "label": "", "needs_password": False,
            "hint": "This order is complete. Corrections require an amended report."}


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


# ── Configuration: tests, queues, retention ──────────────────────────────────
