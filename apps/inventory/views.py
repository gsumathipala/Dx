"""Reagent inventory and in-house manufacturing."""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES
from apps.common.views import DxCreateView, DxListView, DxUpdateView
from apps.inventory.models import InventoryItem, InventoryTransaction, ProductionRun, Recipe
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


class InventoryListView(DxListView):
    model = InventoryItem
    required_roles = LAB_STAFF
    template_name = "inventory/list.html"
    page_title = "Inventory"
    search_fields = ["name", "lot_number", "location"]
    columns = [
        ("Item", "name", ""), ("Lot", "lot_number", "mono"),
        ("Quantity", "quantity", ""), ("Unit", "unit", ""),
        ("Threshold", "min_threshold", ""), ("Low", "is_low", ""),
        ("Expires", "expiration_date", "nowrap"), ("Expired", "is_expired", ""),
        ("Location", "location", ""),
    ]
    create_url_name = "inventory:create"
    update_url_name = "inventory:update"


class InventoryCreateView(DxCreateView):
    model = InventoryItem
    form_class = InventoryItemForm
    required_roles = LAB_STAFF
    page_title = "inventory item"
    success_url = reverse_lazy("inventory:list")


class InventoryUpdateView(DxUpdateView):
    model = InventoryItem
    form_class = InventoryItemForm
    required_roles = LAB_STAFF
    page_title = "inventory item"
    success_url = reverse_lazy("inventory:list")


@login_required
def adjust(request, pk):
    """Restock or correct an item's stock level."""
    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit stock adjustment.")
        return redirect("inventory:list")

    item = get_object_or_404(InventoryItem, pk=pk)
    form = StockAdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        adjust_stock(item, form.cleaned_data["change"], form.cleaned_data["reason"], request.user.username)
        messages.success(request, f"{item.name} adjusted by {form.cleaned_data['change']:+d}.")
        return redirect("inventory:list")

    return render(request, "inventory/adjust.html", {
        "item": item,
        "form": form,
        "transactions": item.transactions.all()[:25],
    })


class TransactionListView(DxListView):
    model = InventoryTransaction
    required_roles = LAB_STAFF
    page_title = "Stock movements"
    search_fields = ["item__name", "reason", "user_id"]
    columns = [
        ("When", "timestamp", "nowrap"), ("Item", "item.name", ""),
        ("Change", "change", ""), ("Balance after", "balance_after", ""),
        ("Reason", "reason", ""), ("By", "user_id", ""),
    ]

    def get_queryset(self):
        return super().get_queryset().select_related("item")


class RecipeListView(DxListView):
    model = Recipe
    required_roles = LAB_STAFF
    page_title = "Manufacturing recipes"
    search_fields = ["name"]
    columns = [("Name", "name", ""), ("Yield", "yield_amount", ""),
               ("Shelf life (days)", "shelf_life_days", ""), ("Active", "active", "")]
    create_url_name = "inventory:recipe_create"
    update_url_name = "inventory:recipe_update"


class RecipeCreateView(DxCreateView):
    model = Recipe
    form_class = RecipeForm
    required_roles = MANAGERS
    page_title = "recipe"
    success_url = reverse_lazy("inventory:recipes")


class RecipeUpdateView(DxUpdateView):
    model = Recipe
    form_class = RecipeForm
    required_roles = MANAGERS
    page_title = "recipe"
    success_url = reverse_lazy("inventory:recipes")


class ProductionListView(DxListView):
    model = ProductionRun
    required_roles = LAB_STAFF
    page_title = "Production runs"
    search_fields = ["batch_number", "recipe__name"]
    columns = [
        ("Batch", "batch_number", "mono"), ("Recipe", "recipe.name", ""),
        ("Quantity", "quantity", ""), ("Status", "status", ""),
        ("QC passed", "qc_passed", ""), ("Expiry", "expiry_date", "nowrap"),
        ("Operator", "operator", ""),
    ]
    create_url_name = "inventory:production_create"
    update_url_name = "inventory:production_update"

    def get_queryset(self):
        return super().get_queryset().select_related("recipe")


class ProductionCreateView(DxCreateView):
    model = ProductionRun
    form_class = ProductionRunForm
    required_roles = LAB_STAFF
    page_title = "production run"
    success_url = reverse_lazy("inventory:production")


class ProductionUpdateView(DxUpdateView):
    model = ProductionRun
    form_class = ProductionRunForm
    required_roles = LAB_STAFF
    page_title = "production run"
    success_url = reverse_lazy("inventory:production")
