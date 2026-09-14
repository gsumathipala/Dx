"""Billing catalogue and invoicing."""
from __future__ import annotations

from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from apps.billing.models import BillingItem, Invoice, InvoiceLine
from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES, Role
from apps.common.views import DxCreateView, DxListView, DxUpdateView

BILLING_ROLES = tuple(LAB_STAFF_ROLES) + (Role.CLERK,)
MANAGERS = tuple(MANAGEMENT_ROLES)


class BillingItemForm(forms.ModelForm):
    class Meta:
        model = BillingItem
        fields = ["code", "name", "price", "tests", "active"]

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price < 0:
            raise forms.ValidationError("A price cannot be negative.")
        return price


class InvoiceListView(DxListView):
    model = Invoice
    required_roles = BILLING_ROLES
    template_name = "billing/list.html"
    page_title = "Invoices"
    search_fields = ["order__accession_number", "order__patient__mrn"]
    filter_fields = {"status": "status"}
    columns = [
        ("Created", "created_at", "nowrap"), ("Accession", "order.accession_number", "mono"),
        ("Patient", "order.patient.full_name", ""), ("Total", "total_amount", "right"),
        ("Paid", "amount_paid", "right"), ("Balance", "balance", "right"),
        ("Status", "status", ""),
    ]

    def get_queryset(self):
        return super().get_queryset().select_related("order", "order__patient")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        totals = Invoice.objects.aggregate(billed=Sum("total_amount"), collected=Sum("amount_paid"))
        context["billed"] = totals["billed"] or Decimal("0.00")
        context["collected"] = totals["collected"] or Decimal("0.00")
        context["outstanding"] = context["billed"] - context["collected"]
        return context


class BillingItemListView(DxListView):
    model = BillingItem
    required_roles = MANAGERS
    page_title = "Billing catalogue"
    search_fields = ["code", "name"]
    columns = [("Code", "code", "mono"), ("Name", "name", ""),
               ("Price", "price", "right"), ("Active", "active", "")]
    create_url_name = "billing:item_create"
    update_url_name = "billing:item_update"


class BillingItemCreateView(DxCreateView):
    model = BillingItem
    form_class = BillingItemForm
    required_roles = MANAGERS
    page_title = "billing item"
    success_url = reverse_lazy("billing:items")


class BillingItemUpdateView(DxUpdateView):
    model = BillingItem
    form_class = BillingItemForm
    required_roles = MANAGERS
    page_title = "billing item"
    success_url = reverse_lazy("billing:items")


@login_required
def generate_invoice(request, order_pk):
    """Raise an invoice for an order from the billing catalogue."""
    from apps.laboratory.models import Order

    if request.user.role not in BILLING_ROLES:
        messages.error(request, "Your role does not permit invoicing.")
        return redirect("billing:list")

    order = get_object_or_404(Order.objects.prefetch_related("tests"), pk=order_pk)
    if Invoice.objects.filter(order=order).exists():
        messages.warning(request, f"{order.accession_number} has already been invoiced.")
        return redirect("billing:list")

    lines, total = [], Decimal("0.00")
    for test in order.tests.all():
        item = BillingItem.objects.filter(tests=test, active=True).first()
        if item is None:
            continue
        lines.append(item)
        total += item.price

    if not lines:
        messages.error(
            request,
            f"No billing catalogue entry covers the tests on {order.accession_number}.",
        )
        return redirect("billing:list")

    invoice = Invoice.objects.create(order=order, total_amount=total)
    for item in lines:
        InvoiceLine.objects.create(
            invoice=invoice, billing_item=item, code=item.code,
            description=item.name, unit_price=item.price,
        )

    messages.success(request, f"Invoice raised for {order.accession_number}: {total}.")
    return redirect("billing:list")
