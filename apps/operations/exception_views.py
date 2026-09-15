"""The unified exception queue: one screen for everything that needs attention.

The list is ordered by severity then age, which is the order a laboratory
actually works: a critical value that has been sitting for forty minutes comes
before a webhook that has been failing for a day, regardless of which was
raised first.
"""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.db.models import Case, Count, IntegerField, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.common.constants import LAB_STAFF_ROLES
from apps.common.views import DxListView, role_required
from apps.operations.exceptions import acknowledge, resolve
from apps.operations.models import ExceptionItem, ExceptionSource

LAB = tuple(LAB_STAFF_ROLES)

#: Severity has to sort by importance, and a text column does not.
SEVERITY_RANK = Case(
    When(severity=ExceptionItem.Severity.CRITICAL, then=Value(0)),
    When(severity=ExceptionItem.Severity.HIGH, then=Value(1)),
    When(severity=ExceptionItem.Severity.MEDIUM, then=Value(2)),
    default=Value(3),
    output_field=IntegerField(),
)


class ResolutionForm(forms.Form):
    resolution = forms.CharField(
        label="What was done",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=(
            "The next person to meet this fault reads this. "
            "'Resolved' on its own helps nobody."
        ),
    )
    dismiss = forms.BooleanField(
        label="Dismiss instead of resolving", required=False,
        help_text="Use this when the item did not represent a real problem.",
    )
    raise_capa = forms.BooleanField(
        label="Raise a corrective action", required=False,
        help_text="For anything with patient impact or a likely recurrence.",
    )


class ExceptionListView(DxListView):
    model = ExceptionItem
    required_roles = LAB
    page_title = "Exception queue"
    page_subtitle = (
        "Everything in the laboratory that needs a person, in one place — "
        "rejected specimens, unacknowledged criticals, breached turnaround, "
        "failed QC, silent interfaces and failing integrations."
    )
    template_name = "operations/exception_list.html"
    search_fields = ["title", "detail", "test_code"]
    filter_fields = {"source": "source", "severity": "severity", "status": "status"}
    columns = [
        ("Raised", "raised_at", "nowrap"),
        ("Severity", "get_severity_display", ""),
        ("Source", "get_source_display", ""),
        ("What", "title", ""),
        ("Accession", "accession", "mono"),
        ("Status", "get_status_display", ""),
    ]
    select_related_extra = ("order", "assigned_to")

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.GET.get("status"):
            queryset = queryset.open()
        if self.request.GET.get("mine") == "1":
            queryset = queryset.filter(assigned_to=self.request.user)
        return queryset.annotate(severity_rank=SEVERITY_RANK).order_by(
            "severity_rank", "raised_at"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = (
            ExceptionItem.objects.open()
            .values("source")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        labels = dict(ExceptionSource.choices)
        context["by_source"] = [
            {"label": labels.get(row["source"], row["source"]), "total": row["total"],
             "source": row["source"]}
            for row in counts
        ]
        context["severities"] = ExceptionItem.Severity.choices
        context["sources"] = ExceptionSource.choices
        context["open_total"] = ExceptionItem.objects.open().count()
        context["overdue_total"] = ExceptionItem.objects.overdue().count()
        return context


@role_required(*LAB)
def exception_detail(request, pk):
    item = get_object_or_404(
        ExceptionItem.objects.select_related(
            "order", "patient", "assigned_to", "acknowledged_by", "resolved_by",
            "corrective_action",
        ),
        pk=pk,
    )
    return render(request, "operations/exception_detail.html", {
        "item": item,
        "form": ResolutionForm(),
    })


@require_POST
@role_required(*LAB)
def exception_acknowledge(request, pk):
    item = get_object_or_404(ExceptionItem, pk=pk)
    if not item.is_open:
        messages.info(request, "That item is already closed.")
    else:
        acknowledge(item, request.user)
        messages.success(request, "Acknowledged — it is now assigned to you.")
    return redirect("operations:exception_detail", pk=item.pk)


@require_POST
@role_required(*LAB)
def exception_resolve(request, pk):
    from apps.compliance.services import ControlViolation

    item = get_object_or_404(ExceptionItem, pk=pk)
    form = ResolutionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Say what was done before closing the item.")
        return redirect("operations:exception_detail", pk=item.pk)

    try:
        resolve(
            item,
            request.user,
            resolution=form.cleaned_data["resolution"],
            dismissed=form.cleaned_data["dismiss"],
            raise_capa=form.cleaned_data["raise_capa"],
        )
    except ControlViolation as violation:
        messages.error(request, str(violation))
        return redirect("operations:exception_detail", pk=item.pk)

    messages.success(
        request,
        "Dismissed." if form.cleaned_data["dismiss"] else "Resolved.",
    )
    return redirect("operations:exception_list")
