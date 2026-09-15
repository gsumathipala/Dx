"""Screens for administering API clients and webhook subscriptions.

Deliberately administrator-only, and deliberately not part of the installer's
world: issuing a credential that can read patient records is a clinical
governance decision, not a maintenance task.
"""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.api.models import PHI_SCOPES, ApiClient, Scope, Webhook, WebhookDelivery
from apps.common.constants import Role
from apps.common.views import DxListView, role_required

ADMINS = (Role.ADMIN,)


class ApiClientForm(forms.ModelForm):
    scopes = forms.MultipleChoiceField(
        choices=Scope.choices, widget=forms.CheckboxSelectMultiple, required=False,
        help_text="Grant the least that will do the job — HIPAA §164.502(b).",
    )

    class Meta:
        model = ApiClient
        fields = ["name", "description", "organisation", "purpose", "owner",
                  "scopes", "rate_limit_per_minute", "expires_at", "active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        cleaned = super().clean()
        scopes = cleaned.get("scopes") or []
        if set(scopes) & PHI_SCOPES and not (cleaned.get("purpose") or "").strip():
            raise forms.ValidationError(
                "A client that can read patient data must say why it exists. "
                "The purpose appears on the disclosure record."
            )
        return cleaned


class WebhookForm(forms.ModelForm):
    events = forms.MultipleChoiceField(
        choices=Webhook.Event.choices, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Webhook
        fields = ["name", "url", "events", "client", "include_identifiers", "active"]

    def clean_url(self):
        url = self.cleaned_data["url"]
        if not url.startswith("https://"):
            raise forms.ValidationError(
                "Use HTTPS. Event payloads can carry patient data."
            )
        return url


class ApiClientListView(DxListView):
    model = ApiClient
    required_roles = ADMINS
    page_title = "API clients"
    page_subtitle = (
        "Named machine consumers of the API. Each is scoped, rate-limited, "
        "revocable and logged."
    )
    template_name = "api/client_list.html"
    columns = [
        ("Name", "name", ""),
        ("Organisation", "organisation", ""),
        ("Key id", "key_id", "mono"),
        ("Scopes", "scope_display", "muted"),
        ("Last used", "last_used_at", "nowrap"),
        ("Active", "active", ""),
    ]
    search_fields = ["name", "organisation", "key_id"]
    create_url_name = "integrations:client_create"
    update_url_name = "integrations:client_update"
    empty_message = "No API clients have been issued."


@role_required(*ADMINS)
def client_create(request):
    form = ApiClientForm(request.POST or None)
    secret = None
    if request.method == "POST" and form.is_valid():
        fields = {
            key: value for key, value in form.cleaned_data.items()
            if key not in {"scopes"}
        }
        client, secret = ApiClient.issue(scopes=list(form.cleaned_data["scopes"]), **fields)
        messages.success(
            request,
            f"{client.name} issued. Copy the token below — it is shown once and "
            "cannot be retrieved afterwards.",
        )
        return render(request, "api/client_secret.html", {"client": client, "secret": secret})

    return render(request, "api/client_form.html", {
        "form": form, "page_title": "New API client", "is_update": False,
    })


@role_required(*ADMINS)
def client_update(request, pk):
    client = get_object_or_404(ApiClient, pk=pk)
    form = ApiClientForm(request.POST or None, instance=client, initial={"scopes": client.scopes})
    if request.method == "POST" and form.is_valid():
        client = form.save(commit=False)
        client.scopes = list(form.cleaned_data["scopes"])
        client.save()
        messages.success(request, "Updated.")
        return redirect("integrations:client_list")
    return render(request, "api/client_form.html", {
        "form": form, "page_title": client.name, "is_update": True, "client": client,
    })


@require_POST
@role_required(*ADMINS)
def client_rotate(request, pk):
    client = get_object_or_404(ApiClient, pk=pk)
    secret = client.rotate_secret()
    messages.warning(
        request,
        "The previous credential stopped working the moment you pressed that. "
        "Give the new one to the client before they next call.",
    )
    return render(request, "api/client_secret.html", {"client": client, "secret": secret})


class WebhookListView(DxListView):
    model = Webhook
    required_roles = ADMINS
    page_title = "Webhooks"
    page_subtitle = (
        "Signed HTTP callbacks. Identifiers are stripped unless a subscription "
        "explicitly asks for them."
    )
    template_name = "api/webhook_list.html"
    columns = [
        ("Name", "name", ""),
        ("URL", "url", "mono"),
        ("Client", "client.name", ""),
        ("Failures", "consecutive_failures", "right"),
        ("Active", "active", ""),
    ]
    search_fields = ["name", "url"]
    create_url_name = "integrations:webhook_create"
    update_url_name = "integrations:webhook_update"
    delete_url_name = "integrations:webhook_delete"
    empty_message = "No webhook subscriptions."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent"] = (
            WebhookDelivery.objects.select_related("webhook").order_by("-created_at")[:25]
        )
        context["failing"] = WebhookDelivery.objects.filter(
            status=WebhookDelivery.Status.FAILED
        ).count()
        return context
