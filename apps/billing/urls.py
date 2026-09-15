from django.urls import path

from apps.billing import views
from apps.billing.models import BillingItem
from apps.common.views import CrudResource

app_name = "billing"

catalogue = CrudResource(
    "item", BillingItem, views.BillingItemForm,
    roles=views.MANAGERS, title="Billing catalogue", singular="billing item",
    columns=[("Code", "code", "mono"), ("Name", "name", ""),
             ("Price", "price", "right"), ("Active", "active", "")],
    search_fields=["code", "name"],
)

urlpatterns = [
    path("", views.InvoiceListView.as_view(), name="invoice_list"),
    *catalogue.urls("catalogue/"),
    path("generate/<str:order_pk>/", views.generate_invoice, name="generate"),
]
