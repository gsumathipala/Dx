"""Administration routes for API clients and webhooks.

Separate from ``apps.api.urls`` — those are the machine-facing endpoints under
/api/v1/, these are screens a human uses.
"""
from django.urls import path

from apps.api import manage_views as views
from apps.api.models import Webhook
from apps.common.views import CrudResource

app_name = "integrations"

webhooks = CrudResource(
    "webhook", Webhook, views.WebhookForm,
    roles=views.ADMINS, title="Webhooks", singular="webhook",
    app_namespace="integrations", deletable=True,
)

urlpatterns = [
    path("clients/", views.ApiClientListView.as_view(), name="client_list"),
    path("clients/new/", views.client_create, name="client_create"),
    path("clients/<str:pk>/rotate/", views.client_rotate, name="client_rotate"),
    path("clients/<str:pk>/", views.client_update, name="client_update"),

    # The list is written out so it can show recent deliveries alongside the
    # subscriptions; the forms come from the factory like every other screen.
    path("webhooks/", views.WebhookListView.as_view(), name="webhook_list"),
    path("webhooks/new/", webhooks.create_view().as_view(), name="webhook_create"),
    path("webhooks/<str:pk>/delete/", webhooks.delete_view().as_view(), name="webhook_delete"),
    path("webhooks/<str:pk>/", webhooks.update_view().as_view(), name="webhook_update"),
]
