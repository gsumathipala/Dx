"""Screens for data subject requests.

Kept deliberately procedural: receive, verify identity, act, close. A GDPR
request is a legal process with a clock on it, and the screen's job is to make
the next required step obvious rather than to offer a menu of options.
"""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.common.constants import MANAGEMENT_ROLES
from apps.common.views import DxListView, role_required
from apps.compliance import subject_rights
from apps.compliance.models import DataSubjectRequest, ProcessingRestriction

MANAGERS = tuple(MANAGEMENT_ROLES)


class SubjectRequestForm(forms.Form):
    mrn = forms.CharField(
        label="Patient MRN",
        help_text="The subject whose data the request concerns.",
    )
    kind = forms.ChoiceField(label="Right being exercised", choices=DataSubjectRequest.Kind.choices)
    requested_by = forms.CharField(
        label="Who asked", help_text="As given — the subject, or their representative."
    )
    relationship = forms.CharField(
        label="Relationship to the subject", initial="self", required=False
    )
    detail = forms.CharField(
        label="What was asked for", widget=forms.Textarea(attrs={"rows": 3}), required=False
    )


class IdentityForm(forms.Form):
    evidence = forms.CharField(
        label="How identity was established",
        help_text=(
            "What was checked — 'passport seen in person', 'known to the ward "
            "team, confirmed by telephone'. Never upload a copy of the document."
        ),
    )


class ExtensionForm(forms.Form):
    reason = forms.CharField(
        label="Why the response needs longer",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="The subject must be told this within the first month.",
    )


class ExportForm(forms.Form):
    passphrase = forms.CharField(
        label="Passphrase for the export", widget=forms.PasswordInput,
        help_text=(
            "The export is encrypted with AES-256-GCM. Give this passphrase to "
            "the subject by a different channel from the file itself — it is "
            "not stored here and cannot be recovered."
        ),
    )
    confirm = forms.CharField(label="Confirm passphrase", widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("passphrase") != cleaned.get("confirm"):
            raise forms.ValidationError("The two passphrases do not match.")
        if len(cleaned.get("passphrase") or "") < 12:
            raise forms.ValidationError(
                "Use at least twelve characters — this file is one person's "
                "entire medical record."
            )
        return cleaned


class RestrictionForm(forms.Form):
    reason = forms.CharField(
        label="Basis for the restriction", widget=forms.Textarea(attrs={"rows": 2})
    )


class SubjectRequestListView(DxListView):
    model = DataSubjectRequest
    required_roles = MANAGERS
    page_title = "Data subject requests"
    page_subtitle = (
        "Access, rectification, erasure, restriction, portability and objection "
        "— with the statutory clock on each."
    )
    template_name = "compliance/subject_request_list.html"
    columns = [
        ("Reference", "reference", "mono"),
        ("Right", "get_kind_display", ""),
        ("Patient", "patient.mrn", "mono"),
        ("Received", "received_at", "nowrap"),
        ("Due", "due_at", "nowrap"),
        ("Status", "get_status_display", ""),
    ]
    search_fields = ["reference", "requested_by", "patient__mrn"]
    filter_fields = {"kind": "kind", "status": "status"}
    empty_message = "No data subject requests have been received."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["overdue_total"] = DataSubjectRequest.objects.overdue().count()
        context["open_total"] = DataSubjectRequest.objects.open().count()
        context["form"] = SubjectRequestForm()
        return context


@require_POST
@role_required(*MANAGERS)
def subject_request_create(request):
    from apps.patients.models import Patient

    form = SubjectRequestForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Check the request details.")
        return redirect("compliance:subject_request_list")

    patient = Patient.objects.filter(mrn=form.cleaned_data["mrn"]).first()
    if patient is None:
        messages.error(request, f"No patient with MRN {form.cleaned_data['mrn']}.")
        return redirect("compliance:subject_request_list")

    record = subject_rights.receive(
        patient=patient,
        kind=form.cleaned_data["kind"],
        requested_by=form.cleaned_data["requested_by"],
        relationship=form.cleaned_data.get("relationship") or "self",
        detail=form.cleaned_data.get("detail") or "",
        user=request.user,
    )
    messages.success(
        request,
        f"{record.reference} logged. The statutory response is due "
        f"{record.due_at:%d %B %Y}. Verify identity before acting on it.",
    )
    return redirect("compliance:subject_request_detail", pk=record.pk)


@role_required(*MANAGERS)
def subject_request_detail(request, pk):
    record = get_object_or_404(
        DataSubjectRequest.objects.select_related(
            "patient", "handled_by", "identity_verified_by", "signature"
        ),
        pk=pk,
    )
    assessment = None
    if record.kind == DataSubjectRequest.Kind.ERASURE and record.is_open:
        assessment = subject_rights.assess_erasure(record.patient)

    restriction = ProcessingRestriction.objects.filter(
        patient=record.patient, lifted_at__isnull=True
    ).first()

    return render(request, "compliance/subject_request_detail.html", {
        "record": record,
        "identity_form": IdentityForm(),
        "extension_form": ExtensionForm(),
        "export_form": ExportForm(),
        "restriction_form": RestrictionForm(),
        "assessment": assessment,
        "restriction": restriction,
        "exportable": record.kind in (
            DataSubjectRequest.Kind.ACCESS, DataSubjectRequest.Kind.PORTABILITY
        ),
    })


@require_POST
@role_required(*MANAGERS)
def subject_request_verify(request, pk):
    from apps.compliance.services import ControlViolation

    record = get_object_or_404(DataSubjectRequest, pk=pk)
    form = IdentityForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Record what was checked.")
        return redirect("compliance:subject_request_detail", pk=record.pk)
    try:
        subject_rights.verify_identity(
            record, user=request.user, evidence=form.cleaned_data["evidence"]
        )
    except ControlViolation as violation:
        messages.error(request, str(violation))
    else:
        messages.success(request, "Identity verified. The request can now be acted on.")
    return redirect("compliance:subject_request_detail", pk=record.pk)


@require_POST
@role_required(*MANAGERS)
def subject_request_extend(request, pk):
    from apps.compliance.services import ControlViolation

    record = get_object_or_404(DataSubjectRequest, pk=pk)
    form = ExtensionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Give a reason for the extension.")
        return redirect("compliance:subject_request_detail", pk=record.pk)
    try:
        subject_rights.extend(record, reason=form.cleaned_data["reason"])
    except ControlViolation as violation:
        messages.error(request, str(violation))
    else:
        messages.success(
            request,
            f"Extended to {record.due_at:%d %B %Y}. Tell the subject within the first month.",
        )
    return redirect("compliance:subject_request_detail", pk=record.pk)


@require_POST
@role_required(*MANAGERS)
def subject_request_export(request, pk):
    record = get_object_or_404(DataSubjectRequest.objects.select_related("patient"), pk=pk)
    if not record.identity_verified:
        messages.error(request, "Verify identity before producing an export.")
        return redirect("compliance:subject_request_detail", pk=record.pk)

    form = ExportForm(request.POST)
    if not form.is_valid():
        for error in form.errors.values():
            messages.error(request, "; ".join(error))
        return redirect("compliance:subject_request_detail", pk=record.pk)

    destination = subject_rights.write_export(
        record, passphrase=form.cleaned_data["passphrase"]
    )
    record.status = DataSubjectRequest.Status.COMPLETED
    record.completed_at = record.completed_at or timezone.now()
    record.handled_by = request.user
    record.outcome = f"Encrypted export written to {destination.name}."
    record.save(update_fields=["status", "completed_at", "handled_by", "outcome"])

    messages.success(
        request,
        f"Export written to {destination}. Send the passphrase separately; "
        "it was not stored.",
    )
    return redirect("compliance:subject_request_detail", pk=record.pk)


@role_required(*MANAGERS)
def subject_request_download(request, pk):
    record = get_object_or_404(DataSubjectRequest, pk=pk)
    if not record.export_path:
        raise Http404("No export has been produced for this request.")
    from pathlib import Path

    path = Path(record.export_path)
    if not path.exists():
        raise Http404("The export file is no longer on disk.")
    return FileResponse(
        path.open("rb"), as_attachment=True, filename=path.name,
        content_type="application/octet-stream",
    )


@require_POST
@role_required(*MANAGERS)
def subject_request_erase(request, pk):
    from apps.compliance.services import ControlViolation

    record = get_object_or_404(DataSubjectRequest.objects.select_related("patient"), pk=pk)
    try:
        assessment = subject_rights.perform_erasure(record, user=request.user)
    except ControlViolation as violation:
        messages.error(request, str(violation))
        return redirect("compliance:subject_request_detail", pk=record.pk)

    if assessment.wholly_refused:
        messages.warning(
            request,
            "Erasure refused in full — every record is still within its "
            "retention period. The basis has been recorded on the request.",
        )
    elif assessment.fully_erasable:
        messages.success(request, f"Erasure completed. {assessment.summary}")
    else:
        messages.warning(request, f"Erasure completed in part. {assessment.summary}")
    return redirect("compliance:subject_request_detail", pk=record.pk)


@require_POST
@role_required(*MANAGERS)
def subject_request_restrict(request, pk):
    record = get_object_or_404(DataSubjectRequest.objects.select_related("patient"), pk=pk)
    form = RestrictionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Give the basis for the restriction.")
        return redirect("compliance:subject_request_detail", pk=record.pk)

    subject_rights.restrict(
        record.patient, reason=form.cleaned_data["reason"], user=request.user, request=record
    )
    record.status = DataSubjectRequest.Status.COMPLETED
    record.outcome = "Processing restricted under Article 18."
    record.handled_by = request.user
    record.save(update_fields=["status", "outcome", "handled_by"])
    messages.success(
        request,
        "Processing restricted. Clinical care continues — Article 18(2) "
        "permits it, and blocking it would endanger the subject.",
    )
    return redirect("compliance:subject_request_detail", pk=record.pk)
