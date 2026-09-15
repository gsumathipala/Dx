from django.urls import path

from apps.common.views import CrudResource
from apps.inventory import views
from apps.inventory.models import InventoryItem, InventoryTransaction, ProductionRun, Recipe

app_name = "inventory"

items = CrudResource(
    "item", InventoryItem, views.InventoryItemForm,
    roles=views.LAB_STAFF, title="Inventory", singular="inventory item",
    list_template="inventory/list.html",
    columns=[("Item", "name", ""), ("Lot", "lot_number", "mono"),
             ("Quantity", "quantity", ""), ("Unit", "unit", ""),
             ("Threshold", "min_threshold", ""), ("Low", "is_low", ""),
             ("Expires", "expiration_date", "nowrap"), ("Expired", "is_expired", ""),
             ("Location", "location", "")],
    search_fields=["name", "lot_number", "location"],
)

transactions = CrudResource(
    "transaction", InventoryTransaction, None,
    roles=views.LAB_STAFF, title="Stock movements",
    columns=[("When", "timestamp", "nowrap"), ("Item", "item.name", ""),
             ("Change", "change", ""), ("Balance after", "balance_after", ""),
             ("Reason", "reason", ""), ("By", "user_id", "")],
    search_fields=["item__name", "reason", "user_id"],
)

recipes = CrudResource(
    "recipe", Recipe, views.RecipeForm,
    roles=views.MANAGERS, title="Manufacturing recipes", singular="recipe",
    columns=[("Name", "name", ""), ("Yield", "yield_amount", ""),
             ("Shelf life (days)", "shelf_life_days", ""), ("Active", "active", "")],
    search_fields=["name"],
)

production = CrudResource(
    "production", ProductionRun, views.ProductionRunForm,
    roles=views.LAB_STAFF, title="Production runs", singular="production run",
    columns=[("Batch", "batch_number", "mono"), ("Recipe", "recipe.name", ""),
             ("Quantity", "quantity", ""), ("Status", "status", ""),
             ("QC passed", "qc_passed", ""), ("Expiry", "expiry_date", "nowrap"),
             ("Operator", "operator", "")],
    search_fields=["batch_number", "recipe__name"],
)

urlpatterns = [
    # Named paths first: `items` is mounted at the root, so its `<pk>/` pattern
    # would otherwise swallow "recipes/", "production/" and the rest.
    *transactions.urls("transactions/"),
    *recipes.urls("recipes/"),
    *production.urls("production/"),
    path("<str:pk>/adjust/", views.adjust, name="item_adjust"),
    *items.urls(""),
]
