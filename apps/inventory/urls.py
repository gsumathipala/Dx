from django.urls import path

from apps.inventory import views

app_name = "inventory"

urlpatterns = [
    path("", views.InventoryListView.as_view(), name="list"),
    path("new/", views.InventoryCreateView.as_view(), name="create"),
    path("transactions/", views.TransactionListView.as_view(), name="transactions"),
    path("recipes/", views.RecipeListView.as_view(), name="recipes"),
    path("recipes/new/", views.RecipeCreateView.as_view(), name="recipe_create"),
    path("recipes/<str:pk>/", views.RecipeUpdateView.as_view(), name="recipe_update"),
    path("production/", views.ProductionListView.as_view(), name="production"),
    path("production/new/", views.ProductionCreateView.as_view(), name="production_create"),
    path("production/<str:pk>/", views.ProductionUpdateView.as_view(), name="production_update"),
    path("<str:pk>/adjust/", views.adjust, name="adjust"),
    path("<str:pk>/", views.InventoryUpdateView.as_view(), name="update"),
]
