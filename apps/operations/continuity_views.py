"""Downtime declaration, backloading and read-only mode."""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES, Role
from apps.common.views import DxListView, role_required
from apps.operations import continuity
from apps.operations.models import DowntimeEvent, DowntimePack

MANAGERS = tuple(MANAGEMENT_ROLES)
#: Declaring downtime and lifting read-only mode are system acts, so the
#: installer can do them — an outage is frequently noticed by whoever
#: maintains the server, at three in the morning, with no manager awake.
SYSTEM = tuple(dict.fromkeys(MANAGERS + (Role.INSTALLER,)))
LAB = tuple(LAB_STAFF_ROLES)


class DeclareForm(forms.Form):
    kind = forms.ChoiceField(choices=DowntimeEvent.Kind.choices,
                             initial=DowntimeEvent.Kind.UNPLANNED)
    began_at = forms.DateTimeField(
        label="When the system was actually lost",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text=(
            "Not when you are logging it. Turnaround figures and the "
            "reconciliation window both depend on the real time."
        ),
    )
    expected_end = forms.DateTimeField(
        required=False, label="Expected back",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="What happened, in the words you would use to an inspector.",
    )
    impact = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        label="What is affected",
    )
    read_only = forms.BooleanField(
        required=False, initial=False,
        label="Also put the system into read-only mode",
        help_text=(
            "For a partial outage where the application is still reachable but "
            "must not be written to — during a restore, for instance."
        ),
    )


class EndForm(forms.Form):
    recovery_notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        label="How it was restored",
    )


class ReconcileForm(forms.Form):
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}), required=False,
        label="Reconciliation notes",
    )
    confirm = forms.BooleanField(
        label="Every result produced on paper during this outage is now in the system",
    )


class ReadOnlyForm(forms.Form):
    reason = forms.CharField(
        label="Why", widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Shown to everyone who tries to save anything.",
    )


class BackloadForm(forms.Form):
    """Entering a paper result afterwards records two people, not one."""

    accession_number = forms.CharField(label="Accession number")
    performed_by = forms.CharField(
        label="Who performed the test",
        help_text=(
            "The person who ran it and wrote the number down — not you, unless "
            "they are the same person. This is the name the report carries."
        ),
    )
    performed_at = forms.DateTimeField(
        label="When it was produced",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    values = forms.CharField(
        label="Results",
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="One per line, as CODE = VALUE. For example: K = 4.2",
    )

    def clean_performed_at(self):
        when = self.cleaned_data["performed_at"]
        if when > timezone.now():
            raise forms.ValidationError("A result cannot have been produced in the future.")
        return when

    def parsed_values(self) -> dict[str, str]:
        """Map the CODE = VALUE lines onto test ids."""
        from apps.laboratory.models import TestDefinition

        parsed: dict[str, str] = {}
        unknown: list[str] = []
        for line in (self.cleaned_data["values"] or "").splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            code, _, value = line.partition("=")
            test = TestDefinition.objects.filter(code__iexact=code.strip()).first()
            if test is None:
                unknown.append(code.strip())
                continue
            parsed[test.id] = value.strip()
        self.unknown_codes = unknown
        return parsed


# ── Screens ──────────────────────────────────────────────────────────────────


class DowntimeListView(DxListView):
    model = DowntimeEvent
    required_roles = SYSTEM
    page_title = "Downtime record"
    page_subtitle = (
        "Every period the laboratory worked without the system, and whether "
        "the paper results have been reconciled."
    )
    template_name = "operations/downtime_list.html"
    columns = [
        ("Reference", "reference", "mono"),
        ("Kind", "get_kind_display", ""),
        ("Began", "began_at", "nowrap"),
        ("Ended", "ended_at", "nowrap"),
        ("Backloaded", "backloaded_results", "right"),
        ("Reconciled", "reconciled_at", "nowrap"),
    ]
    search_fields = ["reference", "reason"]
    filter_fields = {"kind": "kind"}
    empty_message = "No downtime has been recorded. Record drills here too."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current"] = DowntimeEvent.objects.current()
        context["declare_form"] = DeclareForm(initial={"began_at": timezone.now()})
        context["read_only_reason"] = continuity.read_only_reason()
        context["read_only_form"] = ReadOnlyForm()
        context["latest_pack"] = DowntimePack.objects.first()
        context["unreconciled"] = DowntimeEvent.objects.filter(
            ended_at__isnull=False, reconciled_at__isnull=True
        ).count()
        return context


@require_POST
@role_required(*SYSTEM)
def declare(request):
    form = DeclareForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Check the downtime details.")
        return redirect("operations:downtime_list")

    event = continuity.declare(
        kind=form.cleaned_data["kind"],
        reason=form.cleaned_data["reason"],
        user=request.user,
        began_at=form.cleaned_data["began_at"],
        expected_end=form.cleaned_data.get("expected_end"),
        impact=form.cleaned_data.get("impact") or "",
    )
    if form.cleaned_data.get("read_only"):
        continuity.set_read_only(
            f"{event.reference}: {event.reason}", user=request.user
        )
        messages.warning(request, "The system is now read-only. Nothing can be saved.")

    messages.success(
        request,
        f"{event.reference} declared. Record paper results against it once the "
        "system is back — it stays on the exception queue until reconciled.",
    )
    return redirect("operations:downtime_detail", pk=event.pk)


@role_required(*SYSTEM)
def downtime_detail(request, pk):
    event = get_object_or_404(
        DowntimeEvent.objects.select_related(
            "declared_by", "ended_by", "reconciled_by", "corrective_action"
        ),
        pk=pk,
    )
    return render(request, "operations/downtime_detail.html", {
        "event": event,
        "end_form": EndForm(),
        "reconcile_form": ReconcileForm(),
        "read_only_reason": continuity.read_only_reason(),
    })


@require_POST
@role_required(*SYSTEM)
def downtime_end(request, pk):
    event = get_object_or_404(DowntimeEvent, pk=pk)
    form = EndForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Say how the system was restored.")
        return redirect("operations:downtime_detail", pk=event.pk)

    continuity.end(event, user=request.user,
                   recovery_notes=form.cleaned_data["recovery_notes"])
    if continuity.is_read_only():
        continuity.set_read_only(None, user=request.user)
        messages.info(request, "Read-only mode lifted.")

    messages.success(
        request,
        "System recorded as restored. The outage is not closed until every "
        "paper result is in — it is on the exception queue until you reconcile it.",
    )
    return redirect("operations:downtime_detail", pk=event.pk)


@require_POST
@role_required(*SYSTEM)
def downtime_reconcile(request, pk):
    from apps.compliance.services import ControlViolation

    event = get_object_or_404(DowntimeEvent, pk=pk)
    form = ReconcileForm(request.POST)
    if not form.is_valid():
        messages.error(
            request,
            "Confirm that every paper result is in before closing the outage.",
        )
        return redirect("operations:downtime_detail", pk=event.pk)

    try:
        continuity.reconcile(event, user=request.user,
                             notes=form.cleaned_data.get("notes") or "")
    except ControlViolation as violation:
        messages.error(request, str(violation))
    else:
        messages.success(request, f"{event.reference} reconciled and closed.")
    return redirect("operations:downtime_detail", pk=event.pk)


@role_required(*LAB)
def backload(request, pk):
    """Enter results recorded on paper during an outage."""
    from apps.compliance.services import ControlViolation
    from apps.laboratory.models import Order

    event = get_object_or_404(DowntimeEvent, pk=pk)
    form = BackloadForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        order = Order.objects.filter(
            accession_number=form.cleaned_data["accession_number"]
        ).first()
        values = form.parsed_values()

        if order is None:
            messages.error(
                request,
                f"No order with accession number {form.cleaned_data['accession_number']}.",
            )
        elif form.unknown_codes:
            messages.error(
                request,
                "Unknown test code(s): " + ", ".join(form.unknown_codes),
            )
        elif not values:
            messages.error(request, "No results were recognised. Use CODE = VALUE per line.")
        else:
            try:
                written = continuity.backload(
                    order=order,
                    values=values,
                    event=event,
                    performed_by=form.cleaned_data["performed_by"],
                    performed_at=form.cleaned_data["performed_at"],
                    keyed_by=request.user,
                )
            except ControlViolation as violation:
                messages.error(request, str(violation))
            else:
                messages.success(
                    request,
                    f"{len(written)} result(s) entered against {order.accession_number}, "
                    f"attributed to {form.cleaned_data['performed_by']}. They still "
                    "need validating and verifying in the normal way.",
                )
                return redirect("operations:downtime_backload", pk=event.pk)

    return render(request, "operations/downtime_backload.html", {
        "event": event,
        "form": form,
    })


@require_POST
@role_required(*SYSTEM)
def toggle_read_only(request):
    if continuity.is_read_only():
        continuity.set_read_only(None, user=request.user)
        messages.success(request, "Read-only mode lifted. The system accepts writes again.")
        return redirect("operations:downtime_list")

    form = ReadOnlyForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Give a reason — everyone who tries to save will see it.")
        return redirect("operations:downtime_list")

    continuity.set_read_only(form.cleaned_data["reason"], user=request.user)
    messages.warning(
        request,
        "The system is read-only. Nothing can be saved until this is lifted.",
    )
    return redirect("operations:downtime_list")


@require_POST
@role_required(*SYSTEM)
def generate_pack(request):
    pack = continuity.write_pack(generated_by=request.user.username)
    messages.success(
        request,
        f"Downtime pack written to {pack.path} — {pack.order_count} outstanding "
        f"order(s). Make sure it reaches somewhere readable when the server is not.",
    )
    return redirect("operations:downtime_list")


@role_required(*SYSTEM)
def download_pack(request, pk):
    from pathlib import Path

    pack = get_object_or_404(DowntimePack, pk=pk)
    path = Path(pack.path)
    if not path.exists():
        raise Http404("That pack is no longer on disk.")
    return FileResponse(
        path.open("rb"), as_attachment=True, filename=path.name,
        content_type="application/octet-stream" if pack.encrypted else "text/html",
    )
