"""Reagent and consumable inventory, plus media/reagent manufacturing."""
from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.common.models import ActivatableModel, IdentifiedModel


class InventoryItem(IdentifiedModel):
    """A reagent or consumable, with its lot and expiry.

    Lot and expiry are the regulated part, not the stock count. CLIA and CAP
    both require a result to be traceable to the reagent lot that produced it,
    which is why consumption is recorded per test rather than per delivery.
    """

    name = models.CharField(max_length=255)
    lot_number = models.CharField(max_length=64, null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    quantity = models.IntegerField(default=0)
    unit = models.CharField(max_length=64)
    min_threshold = models.IntegerField(default=10)
    location = models.CharField(max_length=255, null=True, blank=True)
    tests = models.ManyToManyField(
        "laboratory.TestDefinition",
        blank=True,
        related_name="reagents",
        help_text="Tests that consume this reagent",
    )

    class Meta:
        db_table = "inventory_items"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.quantity} {self.unit})"

    @property
    def is_low(self) -> bool:
        return self.quantity <= self.min_threshold

    @property
    def is_expired(self) -> bool:
        return bool(self.expiration_date and self.expiration_date < timezone.localdate())

    @property
    def is_usable(self) -> bool:
        return self.quantity > 0 and not self.is_expired


class InventoryTransaction(IdentifiedModel):
    """Every movement in or out, so stock is derived rather than asserted.

    A running total that is edited directly cannot be reconciled when it drifts.
    Recording the movements means the balance is always explicable, and an
    unexpected consumption can be traced to the test that caused it.
    """

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="transactions")
    change = models.IntegerField(help_text="Positive for restock, negative for consumption")
    reason = models.CharField(max_length=255)
    user_id = models.CharField(max_length=150)
    timestamp = models.DateTimeField(default=timezone.now)
    balance_after = models.IntegerField(
        null=True, blank=True, help_text="Stock level after the movement, for reconciliation"
    )

    class Meta:
        db_table = "inventory_transactions"
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["item", "-timestamp"])]

    def __str__(self) -> str:
        return f"{self.item_id} {self.change:+d} ({self.reason})"


class Recipe(IdentifiedModel, ActivatableModel):
    """Formulation for in-house media or reagent production."""

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    ingredients = models.JSONField(default=list, blank=True)
    instructions = models.TextField(null=True, blank=True)
    yield_amount = models.CharField(max_length=128, null=True, blank=True, db_column="yield")
    shelf_life_days = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "recipes"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProductionRun(IdentifiedModel):
    """A batch of media or reagent manufactured in-house.

    In-house manufacture makes the laboratory the manufacturer, so the batch
    needs its own lot number, its inputs recorded, and a release decision
    before use — the same obligations that arrive with a purchased reagent,
    only nobody else is discharging them.
    """

    class Status(models.TextChoices):
        SCHEDULED = "Scheduled", "Scheduled"
        IN_PROGRESS = "In Progress", "In progress"
        QUARANTINE = "Quarantine", "In quarantine (awaiting QC)"
        RELEASED = "Released", "Released"
        FAILED = "Failed", "Failed"

    recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT, related_name="runs")
    batch_number = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.SCHEDULED)
    quantity = models.PositiveIntegerField()
    start_date = models.DateTimeField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    operator = models.CharField(max_length=150, null=True, blank=True)
    qc_passed = models.BooleanField(
        null=True, blank=True, help_text="Sterility/performance check before release"
    )
    released_by = models.CharField(max_length=150, null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "production_runs"
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return f"{self.batch_number} ({self.status})"

    @property
    def can_release(self) -> bool:
        """In-house product may only be released after its QC has passed."""
        return self.status == self.Status.QUARANTINE and self.qc_passed is True
