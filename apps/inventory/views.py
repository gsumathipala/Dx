"""Reagent inventory and in-house manufacturing.

Stock adjustment is written out below; the registries are declared as
``CrudResource`` objects in ``urls.py``.
"""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES
from apps.inventory.models import InventoryItem, ProductionRun, Recipe
from apps.inventory.services import adjust_stock

LAB_STAFF = tuple(LAB_STAFF_ROLES)
MANAGERS = tuple(MANAGEMENT_ROLES)


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ["name", "lot_number", "expiration_date", "quantity", "unit",
                  "min_threshold", "location", "tests"]
        widgets = {"expiration_date": forms.DateInput(attrs={"type": "date"})}


class StockAdjustmentForm(forms.Form):
    change = forms.IntegerField(help_text="Positive to restock, negative to correct downwards.")
    reason = forms.CharField(max_length=255)

    def clean_change(self):
        change = self.cleaned_data["change"]
        if change == 0:
            raise forms.ValidationError("A movement of zero records nothing.")
        return change


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ["name", "description", "ingredients", "instructions",
                  "yield_amount", "shelf_life_days", "active"]


class ProductionRunForm(forms.ModelForm):
    class Meta:
        model = ProductionRun
        fields = ["recipe", "batch_number", "status", "quantity", "start_date",
                  "completion_date", "expiry_date", "operator", "qc_passed"]
        widgets = {
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "completion_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        # In-house product may not be released until its QC has passed.
        if cleaned.get("status") == ProductionRun.Status.RELEASED and cleaned.get("qc_passed") is not True:
            raise forms.ValidationError(
                "A batch cannot be released until its quality control has passed."
            )
        return cleaned


@login_required
def adjust(request, pk):
    """Restock or correct an item's stock level."""
    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit stock adjustment.")
        return redirect("inventory:item_list")

    item = get_object_or_404(InventoryItem, pk=pk)
    form = StockAdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        adjust_stock(item, form.cleaned_data["change"], form.cleaned_data["reason"], request.user.username)
        messages.success(request, f"{item.name} adjusted by {form.cleaned_data['change']:+d}.")
        return redirect("inventory:item_list")

    return render(request, "inventory/adjust.html", {
        "item": item,
        "form": form,
        "transactions": item.transactions.all()[:25],
    })
