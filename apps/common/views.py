"""Reusable view machinery.

The application has a long tail of configuration screens that are all the same
shape: a filtered, paginated list with create/edit/delete behind a role check.
Implementing each by hand would be ~40 near-identical modules, so they share
these bases and the templates in ``templates/generic/``. Screens with real
workflow (result entry, accessioning, QC, the audit trail) are written out in
full instead.

``DxListView`` derives its own ``select_related`` from the column definitions,
so a screen cannot silently acquire an N+1 by naming a related field. See
``relation_paths_for``.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

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


def role_required(*roles: str):
    """Restrict a function view to a set of roles.

    The class-based screens get this from ``RoleRequiredMixin``; the handful of
    function views that carry real workflow need the same check, and writing it
    inline in each is how one of them ends up missing it.
    """
    import functools

    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if user is None or not user.is_authenticated:
                raise PermissionDenied("Sign in first.")
            if roles and user.role not in roles:
                raise PermissionDenied("Your role does not permit access to this screen.")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def request_referer(request, fallback: str = "operations:dashboard") -> str:
    return request.META.get("HTTP_REFERER") or reverse(fallback)


class ControlViolationMixin:
    """Turn a blocked regulatory control into a readable message, not a 500."""

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except ControlViolation as violation:
            messages.error(request, str(violation))
            return self.violation_response(violation)

    def violation_response(self, violation):
        return redirect(request_referer(self.request))


def relation_paths_for(model, column_paths) -> set[str]:
    """Derive ``select_related`` arguments from dotted column paths.

    ``"department.name"`` yields ``"department"``; ``"specimen.order.accession"``
    yields ``"specimen__order"``. Only forward single-valued relations are
    followed — ``select_related`` cannot span a reverse or many-to-many
    relation, and asking it to would raise rather than merely being slow.

    Doing this from the column definitions means a list screen cannot acquire
    an N+1 just by naming a related field, which is how nine of them had.
    """
    paths: set[str] = set()

    for path in column_paths:
        if "." not in path:
            continue

        current = model
        parts: list[str] = []
        for segment in path.split(".")[:-1]:
            try:
                field = current._meta.get_field(segment)
            except (FieldDoesNotExist, AttributeError):
                break
            # many_to_one/one_to_one covers ForeignKey and OneToOneField.
            if not (field.many_to_one or field.one_to_one) or not field.concrete:
                break
            parts.append(segment)
            current = field.related_model

        if parts:
            paths.add("__".join(parts))

    return paths


class DxListView(RoleRequiredMixin, ListView):
    """Paginated, searchable list backed by ``generic/list.html``."""

    paginate_by = 50
    template_name = "generic/list.html"

    #: Column definitions: (header, attribute path, css class)
    columns: list[tuple[str, str, str]] = []
    #: Fields included in the ``?q=`` search.
    search_fields: list[str] = []
    #: Exact-match filters exposed as select boxes: {querystring key: field}
    filter_fields: dict[str, str] = {}
    #: Relations to prefetch that the columns cannot imply (reverse or m2m).
    prefetch_related: tuple[str, ...] = ()
    #: Extra select_related the column paths cannot reveal — typically a
    #: property that walks a relation, such as StorageLocation.path.
    select_related_extra: tuple[str, ...] = ()
    #: Aggregates evaluated in SQL, e.g. {"queued_count": Count("assignments")}.
    #: Use these instead of model properties that query, which run per row.
    annotations: dict = {}

    page_title = ""
    page_subtitle = ""
    create_url_name: str | None = None
    update_url_name: str | None = None
    delete_url_name: str | None = None
    empty_message = "No records yet."

    def get_queryset(self):
        queryset = super().get_queryset()

        relations = relation_paths_for(self.model, [path for _h, path, _c in self.columns])
        relations |= set(self.select_related_extra)
        if relations:
            queryset = queryset.select_related(*sorted(relations))
        if self.prefetch_related:
            queryset = queryset.prefetch_related(*self.prefetch_related)
        if self.annotations:
            queryset = queryset.annotate(**self.annotations)
            # Django drops a model's default ordering when an aggregate
            # annotation is applied, because it would otherwise land in the
            # GROUP BY. Paginating an unordered queryset silently repeats and
            # skips rows between pages, so the ordering is restored explicitly.
            if not queryset.ordered and self.model._meta.ordering:
                queryset = queryset.order_by(*self.model._meta.ordering)

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


class RecordLockMixin:
    """Refuse an edit screen while somebody else has the record open.

    Set ``lock_entity_type`` to the model label the lock is keyed on. The lock
    is taken on GET, so arriving at the form reserves the record, and checked
    again on POST, because the lock may have expired or been broken while the
    form sat open.

    A blocked user is shown the form read-only with an explanation rather than
    being bounced: "Jane has this open" is information, and a redirect to a
    list screen with a red banner is not.
    """

    lock_entity_type: str | None = None

    def dispatch(self, request, *args, **kwargs):
        self.lock_state = None
        if self.lock_entity_type and request.user.is_authenticated:
            from apps.accounts import locking

            self.object = self.get_object()
            self.lock_state = locking.acquire(
                self.lock_entity_type, self.object.pk, request.user
            )
            if request.method == "POST" and not self.lock_state.editable:
                messages.error(request, self.lock_state.message)
                return redirect(request.path)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lock"] = self.lock_state
        context["lock_entity_type"] = self.lock_entity_type
        context["lock_entity_id"] = str(self.object.pk) if getattr(self, "object", None) else ""
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        # The edit is committed; do not hold the record while walking away.
        if self.lock_entity_type:
            from apps.accounts import locking

            locking.release(self.lock_entity_type, self.object.pk, self.request.user)
        return response


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


# ── CRUD resource factory ────────────────────────────────────────────────────


class CrudResource:
    """A list/create/update triple and its URL patterns, from one declaration.

    The configuration screens differ only by model, form, roles and labels.
    Writing each as three classes and three URL entries produced ~650 lines of
    near-identical code, and made it easy for one screen to quietly drift from
    the rest. Declaring a resource keeps the whole screen in one readable
    block:

        tests = CrudResource(
            "test", TestDefinition, TestDefinitionForm,
            roles=MANAGERS, title="Test definitions",
            columns=[("Code", "code", "mono"), ...],
            search_fields=["code", "name"],
        )
        urlpatterns = [..., *tests.urls()]

    Anything with genuine behaviour of its own still subclasses the views
    directly — the factory is for screens that are only configuration.
    """

    def __init__(
        self,
        name: str,
        model,
        form_class,
        *,
        roles=None,
        title: str = "",
        subtitle: str = "",
        columns=(),
        search_fields=(),
        filter_fields=None,
        annotations=None,
        prefetch_related=(),
        select_related_extra=(),
        singular: str = "",
        list_template: str | None = None,
        paginate_by: int = 50,
        on_create=None,
        on_update=None,
        app_namespace: str | None = None,
        deletable: bool = False,
        lock_entity_type: str | None = None,
    ):
        self.name = name
        self.model = model
        self.form_class = form_class
        self.roles = tuple(roles) if roles else None
        self.title = title or model._meta.verbose_name_plural.title()
        self.subtitle = subtitle
        self.columns = list(columns)
        self.search_fields = list(search_fields)
        self.filter_fields = dict(filter_fields or {})
        self.annotations = dict(annotations or {})
        self.prefetch_related = tuple(prefetch_related)
        self.select_related_extra = tuple(select_related_extra)
        self.singular = singular or model._meta.verbose_name
        self.list_template = list_template
        self.paginate_by = paginate_by
        #: Hooks receiving (view, form) just before the object is saved — used
        #: for fields the form does not ask for, such as "raised by".
        self.on_create = on_create
        self.on_update = on_update
        self.namespace = app_namespace or model._meta.app_label
        self.deletable = deletable
        #: When set, the update screen takes a pessimistic record lock. Only
        #: the update screen: creating a record nobody else can name yet
        #: cannot collide with anything.
        self.lock_entity_type = lock_entity_type

    # ── URL names ────────────────────────────────────────────────────────────

    @property
    def list_name(self) -> str:
        return f"{self.name}_list"

    @property
    def create_name(self) -> str:
        return f"{self.name}_create"

    @property
    def update_name(self) -> str:
        return f"{self.name}_update"

    @property
    def delete_name(self) -> str:
        return f"{self.name}_delete"

    def _qualified(self, url_name: str) -> str:
        return f"{self.namespace}:{url_name}"

    # ── Generated views ──────────────────────────────────────────────────────

    def list_view(self):
        resource = self
        attrs = {
            "model": self.model,
            "required_roles": self.roles,
            "page_title": self.title,
            "page_subtitle": self.subtitle,
            "columns": self.columns,
            "search_fields": self.search_fields,
            "filter_fields": self.filter_fields,
            "annotations": self.annotations,
            "prefetch_related": self.prefetch_related,
            "select_related_extra": self.select_related_extra,
            "paginate_by": self.paginate_by,
            "create_url_name": resource._qualified(resource.create_name) if self.form_class else None,
            "update_url_name": resource._qualified(resource.update_name) if self.form_class else None,
            "delete_url_name": resource._qualified(resource.delete_name) if self.deletable else None,
        }
        if self.list_template:
            attrs["template_name"] = self.list_template
        return type(f"{self.model.__name__}ListView", (DxListView,), attrs)

    def _form_view(self, base, hook, message):
        resource = self

        def form_valid(self, form):
            if hook is not None:
                hook(self, form)
            # Bound to the class created below, not to ``type(self)``. With
            # ``type(self)`` a subclass of this view — such as one carrying
            # RecordLockMixin — makes super() resolve back to this same
            # method, and the first save recurses until the stack runs out.
            return super(view, self).form_valid(form)

        view = type(
            f"{self.model.__name__}{base.__name__.replace('Dx', '')}",
            (base,),
            {
                "model": self.model,
                "form_class": self.form_class,
                "required_roles": self.roles,
                "page_title": self.singular,
                "success_message": message,
                "success_url": reverse_lazy(resource._qualified(resource.list_name)),
                "form_valid": form_valid,
            },
        )
        return view

    def create_view(self):
        return self._form_view(DxCreateView, self.on_create, "Created.")

    def update_view(self):
        view = self._form_view(DxUpdateView, self.on_update, "Updated.")
        if self.lock_entity_type:
            view = type(
                view.__name__,
                (RecordLockMixin, view),
                {"lock_entity_type": self.lock_entity_type},
            )
        return view

    def delete_view(self):
        resource = self
        return type(
            f"{self.model.__name__}DeleteView",
            (DxDeleteView,),
            {
                "model": self.model,
                "required_roles": self.roles,
                "success_url": reverse_lazy(resource._qualified(resource.list_name)),
            },
        )

    # ── URL patterns ─────────────────────────────────────────────────────────

    def urls(self, prefix: str | None = None):
        """URL patterns for this resource: list, create, update (and delete).

        The update pattern ends in ``<str:pk>/``, which matches any single
        segment. A resource mounted at a prefix that is a parent of another
        resource's prefix will therefore shadow it, so list the more specific
        resources first in ``urlpatterns``.
        """
        from django.urls import path

        base = prefix if prefix is not None else f"{self.name}s/"
        patterns = [path(base, self.list_view().as_view(), name=self.list_name)]

        if self.form_class:
            patterns += [
                path(f"{base}new/", self.create_view().as_view(), name=self.create_name),
            ]
        if self.deletable:
            patterns.append(
                path(f"{base}<str:pk>/delete/", self.delete_view().as_view(), name=self.delete_name)
            )
        if self.form_class:
            # Registered last so "new/" and "<pk>/delete/" are matched first.
            patterns.append(
                path(f"{base}<str:pk>/", self.update_view().as_view(), name=self.update_name)
            )
        return patterns
