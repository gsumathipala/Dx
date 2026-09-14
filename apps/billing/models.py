"""Billing catalogue and invoicing."""
from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.common.models import ActivatableModel, IdentifiedModel


class BillingItem(IdentifiedModel, ActivatableModel):
    code = models.CharField(max_length=32, unique=True, help_text="CPT-4 or internal billing code")
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    tests = models.ManyToManyField(
        "laboratory.TestDefinition", blank=True, related_name="billing_items"
    )

    class Meta:
        db_table = "billing_items"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class Invoice(IdentifiedModel):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        PAID = "Paid", "Paid"
        PARTIALLY_PAID = "Partially Paid", "Partially paid"
        CANCELLED = "Canceled", "Cancelled"
        WRITTEN_OFF = "Written Off", "Written off"

    order = models.ForeignKey("laboratory.Order", on_delete=models.PROTECT, related_name="invoices")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "invoices"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self) -> str:
        return f"Invoice {self.id} — {self.total_amount}"

    @property
    def balance(self) -> Decimal:
        return self.total_amount - self.amount_paid


class InvoiceLine(IdentifiedModel):
    """One charge on an invoice.

    The legacy schema kept these as a JSON blob, which made revenue reporting
    impossible without parsing every invoice.
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    billing_item = models.ForeignKey(
        BillingItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="lines"
    )
    code = models.CharField(max_length=32)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "invoice_lines"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} x{self.quantity}"

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity
