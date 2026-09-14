"""Forms for the regulatory records."""
from __future__ import annotations

from django import forms
from django.contrib.auth import password_validation

from apps.compliance.models import (
    AmendedReport, ChangeControl, CorrectiveAction, MethodValidation,
    PatientConsent, ProficiencyResult, ProficiencySurvey, RetentionSchedule,
    RiskAssessment, TrainingRecord,
)


class SignatureForm(forms.Form):
    """Password re-entry required to apply an electronic signature."""

    password = forms.CharField(
        widget=forms.PasswordInput, label="Your password",
        help_text="Re-entered at signing — 21 CFR Part 11 §11.200(a)(1).",
    )
    comment = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current = self.cleaned_data["current_password"]
        if not self.user.check_password(current):
            raise forms.ValidationError("Your current password is not correct.")
        return current

    def clean(self):
        cleaned = super().clean()
        new, confirm = cleaned.get("new_password"), cleaned.get("confirm_password")
        if new and confirm and new != confirm:
            raise forms.ValidationError("The new passwords do not match.")
        if new:
            password_validation.validate_password(new, self.user)

            from apps.compliance.services import check_password_reuse

            check = check_password_reuse(self.user, new)
            if not check.allowed:
                raise forms.ValidationError(check.message)
        return cleaned


class CorrectiveActionForm(forms.ModelForm):
    class Meta:
        model = CorrectiveAction
        fields = [
            "title", "category", "severity", "status", "description",
            "immediate_action", "root_cause", "corrective_action",
            "preventive_action", "effectiveness_check", "patient_impact",
            "reported_results_affected", "assigned_to", "due_date",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "immediate_action": forms.Textarea(attrs={"rows": 2}),
            "root_cause": forms.Textarea(attrs={"rows": 2}),
            "corrective_action": forms.Textarea(attrs={"rows": 2}),
            "preventive_action": forms.Textarea(attrs={"rows": 2}),
            "effectiveness_check": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        # A CAPA cannot be closed without the evidence chain that justifies closure.
        if cleaned.get("status") == CorrectiveAction.Status.CLOSED:
            missing = [
                label for field, label in (
                    ("root_cause", "root cause"),
                    ("corrective_action", "corrective action"),
                    ("effectiveness_check", "effectiveness check"),
                ) if not cleaned.get(field)
            ]
            if missing:
                raise forms.ValidationError(
                    "A nonconformance cannot be closed until the "
                    f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} documented."
                )
        return cleaned


class ProficiencySurveyForm(forms.ModelForm):
    class Meta:
        model = ProficiencySurvey
        fields = [
            "provider", "survey_code", "year", "event", "discipline",
            "received_date", "due_date", "submitted_date", "submitted_by",
            "attestation_signed", "notes",
        ]
        widgets = {
            "received_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "submitted_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("submitted_date") and not cleaned.get("attestation_signed"):
            raise forms.ValidationError(
                "A proficiency survey cannot be recorded as submitted without the "
                "attestation that no inter-laboratory communication took place "
                "(CLIA 42 CFR §493.801(b)(4))."
            )
        return cleaned


class ProficiencyResultForm(forms.ModelForm):
    class Meta:
        model = ProficiencyResult
        fields = [
            "survey", "test", "analyte", "sample_id", "reported_value",
            "target_value", "acceptable_range", "z_score", "grade", "corrective_action",
        ]


class MethodValidationForm(forms.ModelForm):
    class Meta:
        model = MethodValidation
        fields = [
            "test", "kind", "instrument", "performed_by", "started_on", "completed_on",
            "accuracy_verified", "precision_verified", "reportable_range_verified",
            "reference_interval_verified", "analytical_sensitivity",
            "analytical_specificity", "summary", "status",
        ]
        widgets = {
            "started_on": forms.DateInput(attrs={"type": "date"}),
            "completed_on": forms.DateInput(attrs={"type": "date"}),
            "summary": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == MethodValidation.Status.APPROVED:
            required = [
                ("accuracy_verified", "accuracy"),
                ("precision_verified", "precision"),
                ("reportable_range_verified", "reportable range"),
                ("reference_interval_verified", "reference interval"),
            ]
            missing = [label for field, label in required if not cleaned.get(field)]
            if missing:
                raise forms.ValidationError(
                    "CLIA 42 CFR §493.1253(b)(1) requires verification of accuracy, "
                    "precision, reportable range and reference interval before a "
                    f"method is approved. Still outstanding: {', '.join(missing)}."
                )
        return cleaned


class RiskAssessmentForm(forms.ModelForm):
    class Meta:
        model = RiskAssessment
        fields = [
            "title", "process_area", "description", "likelihood", "severity",
            "existing_controls", "mitigation", "residual_likelihood",
            "residual_severity", "owner", "status", "reviewed_on", "next_review",
        ]
        widgets = {
            "reviewed_on": forms.DateInput(attrs={"type": "date"}),
            "next_review": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class ChangeControlForm(forms.ModelForm):
    class Meta:
        model = ChangeControl
        fields = [
            "title", "description", "change_type", "impact_assessment",
            "validation_evidence", "rollback_plan", "status",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "impact_assessment": forms.Textarea(attrs={"rows": 3}),
            "validation_evidence": forms.Textarea(attrs={"rows": 3}),
            "rollback_plan": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") in {ChangeControl.Status.IMPLEMENTED, ChangeControl.Status.VERIFIED}:
            if not cleaned.get("validation_evidence"):
                raise forms.ValidationError(
                    "A change affecting result production cannot be recorded as "
                    "implemented without validation evidence "
                    "(21 CFR Part 11 §11.10(a))."
                )
        return cleaned


class TrainingRecordForm(forms.ModelForm):
    class Meta:
        model = TrainingRecord
        fields = [
            "user", "topic", "document", "trainer", "completed_on",
            "expires_on", "status", "assessment_method", "notes",
        ]
        widgets = {
            "completed_on": forms.DateInput(attrs={"type": "date"}),
            "expires_on": forms.DateInput(attrs={"type": "date"}),
        }


class RetentionScheduleForm(forms.ModelForm):
    class Meta:
        model = RetentionSchedule
        fields = ["record_class", "retention_years", "citation", "destruction_method", "notes", "active"]


class AmendedReportForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput, label="Your password",
        help_text="An amended report must be electronically signed.",
    )

    class Meta:
        model = AmendedReport
        fields = ["result", "reason", "original_value", "corrected_value", "narrative"]
        widgets = {"narrative": forms.Textarea(attrs={"rows": 3})}


class PatientConsentForm(forms.ModelForm):
    class Meta:
        model = PatientConsent
        fields = ["patient", "kind", "granted", "recorded_by", "document_reference", "notes"]
