from django.urls import path

from apps.billing import views

app_name = "billing"

urlpatterns = [
    path("", views.InvoiceListView.as_view(), name="list"),
    path("catalogue/", views.BillingItemListView.as_view(), name="items"),
    path("catalogue/new/", views.BillingItemCreateView.as_view(), name="item_create"),
    path("catalogue/<str:pk>/", views.BillingItemUpdateView.as_view(), name="item_update"),
    path("generate/<str:order_pk>/", views.generate_invoice, name="generate"),
]
