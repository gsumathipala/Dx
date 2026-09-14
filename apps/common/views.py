"""Reusable view machinery.

The application has a long tail of configuration screens that are all the same
shape: a filtered, paginated list with create/edit/delete behind a role check.
Implementing each by hand would be ~40 near-identical modules, so they share
these bases and the templates in ``templates/generic/``. Screens with real
workflow (result entry, accessioning, QC, the audit trail) are written out in
full instead.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.compliance.services import ControlViolation


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to a set of roles.

    ``required_roles = None`` means any authenticated user.
    """

    required_roles: tuple[str, ...] | None = None

    def test_func(self) -> bool:
        if self.required_roles is None:
            return True
        return self.request.user.role in self.required_roles

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied(
                "Your role does not permit access to this screen."
            )
        return super().handle_no_permission()


class ControlViolationMixin:
    """Turn a blocked regulatory control into a readable message, not a 500."""

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except ControlViolation as violation:
            messages.error(request, str(violation))
            return self.violation_response(violation)

    def violation_response(self, violation):
        from django.shortcuts import redirect

        return redirect(request_referer(self.request))


def request_referer(request, fallback: str = "operations:dashboard") -> str:
    from django.urls import reverse

    return request.META.get("HTTP_REFERER") or reverse(fallback)


class DxListView(RoleRequiredMixin, ListView):
    """Paginated, searchable list backed by ``generic/list.html``."""

    paginate_by = 50
    template_name = "generic/list.html"

    #: Column definitions: (header, attribute or callable name, css class)
    columns: list[tuple[str, str, str]] = []
    #: Fields included in the ``?q=`` search.
    search_fields: list[str] = []
    #: Exact-match filters exposed as select boxes: {querystring key: field}
    filter_fields: dict[str, str] = {}
    page_title = ""
    page_subtitle = ""
    create_url_name: str | None = None
    update_url_name: str | None = None
    delete_url_name: str | None = None
    empty_message = "No records yet."

    def get_queryset(self):
        queryset = super().get_queryset()

        query = (self.request.GET.get("q") or "").strip()
        if query and self.search_fields:
            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(condition)

        for key, field in self.filter_fields.items():
            value = self.request.GET.get(key)
            if value:
                queryset = queryset.filter(**{field: value})

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        querystring = self.request.GET.copy()
        querystring.pop("page", None)
        context.update({
            "columns": self.columns,
            "page_title": self.page_title or self.model._meta.verbose_name_plural.title(),
            "page_subtitle": self.page_subtitle,
            "search_fields": self.search_fields,
            "create_url_name": self.create_url_name,
            "update_url_name": self.update_url_name,
            "delete_url_name": self.delete_url_name,
            "empty_message": self.empty_message,
            "querystring": querystring.urlencode() + ("&" if querystring else ""),
            "filters": self.request.GET,
            "entity_type": self.model._meta.label,
        })
        return context


class DxFormMixin(RoleRequiredMixin, ControlViolationMixin):
    template_name = "generic/form.html"
    page_title = ""
    success_message = "Saved."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title or f"{self.model._meta.verbose_name.title()}"
        context["is_update"] = getattr(self, "object", None) is not None
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response

    def violation_response(self, violation):
        return self.render_to_response(self.get_context_data(form=self.get_form()))


class DxCreateView(DxFormMixin, CreateView):
    success_message = "Created."


class DxUpdateView(DxFormMixin, UpdateView):
    success_message = "Updated."


class DxDeleteView(RoleRequiredMixin, DeleteView):
    template_name = "generic/confirm_delete.html"
    success_message = "Deleted."

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class DxDetailView(RoleRequiredMixin, DetailView):
    """Detail view that also exposes the record's audit history."""

    def get_context_data(self, **kwargs):
        from apps.audit.models import AuditEvent

        context = super().get_context_data(**kwargs)
        context["audit_events"] = AuditEvent.objects.for_entity(
            self.model._meta.label, self.object.pk
        )[:20]
        context["entity_type"] = self.model._meta.label
        return context
