"""Forms for accessioning, receiving and result entry.

``ResultEntryForm`` is the one to read first: it is built dynamically from the
tests on an order, so its fields do not exist until ``__init__`` has run. That
is why it is a plain ``Form`` rather than a ``ModelForm`` and why ``values()``
exists to map the generated field names back onto test ids.
"""
from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.laboratory.models import (
    AuthorizationQueue, Order, PhlebotomySchedule, RetentionPolicy,
    SpecimenReceiving, TestDefinition,
)


class AccessionForm(forms.Form):
    """Create a new request against an existing patient."""

    patient = forms.ModelChoiceField(queryset=None)
    tests = forms.ModelMultipleChoiceField(
        queryset=TestDefinition.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )
    priority = forms.ChoiceField(choices=Order._meta.get_field("priority").choices)
    ordered_by = forms.CharField(max_length=255, label="Requesting clinician")
    requester = forms.ModelChoiceField(queryset=None, required=False)
    specimen_type = forms.CharField(max_length=128, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from apps.patients.models import Patient
        from apps.reporting.models import Requester

        self.fields["patient"].queryset = Patient.objects.all()
        self.fields["tests"].queryset = TestDefinition.objects.filter(active=True).order_by("code")
        self.fields["requester"].queryset = Requester.objects.filter(active=True)

    def clean_tests(self):
        tests = self.cleaned_data["tests"]
        if not tests:
            raise forms.ValidationError("Select at least one test.")
        return tests


class TestDefinitionForm(forms.ModelForm):
    class Meta:
        model = TestDefinition
        fields = [
            "code", "name", "department", "units", "tat_hours", "reference_range",
            "specimen_types", "methodology", "loinc_code", "active",
        ]
        help_texts = {
            "reference_range": 'JSON, e.g. {"min": 3.9, "max": 5.8, "panicLow": 2.2, "panicHigh": 25}',
            "specimen_types": 'JSON list, e.g. ["Serum", "Plasma"]',
        }

    def clean_reference_range(self):
        data = self.cleaned_data.get("reference_range")
        if not data:
            return data
        if not isinstance(data, dict):
            raise forms.ValidationError("The reference range must be a JSON object.")

        low, high = data.get("min"), data.get("max")
        if isinstance(low, (int, float)) and isinstance(high, (int, float)) and low > high:
            raise forms.ValidationError("The lower bound cannot exceed the upper bound.")

        panic_low, panic_high = data.get("panicLow"), data.get("panicHigh")
        if isinstance(panic_low, (int, float)) and isinstance(low, (int, float)) and panic_low > low:
            raise forms.ValidationError(
                "The critically-low limit must be at or below the lower reference bound."
            )
        if isinstance(panic_high, (int, float)) and isinstance(high, (int, float)) and panic_high < high:
            raise forms.ValidationError(
                "The critically-high limit must be at or above the upper reference bound."
            )
        return data


class ResultEntryForm(forms.Form):
    """Dynamically built from the tests on an order."""

    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}), required=False,
        label="Report comment",
    )
    queue = forms.ModelChoiceField(queryset=AuthorizationQueue.objects.all(), required=False)
    password = forms.CharField(
        widget=forms.PasswordInput, required=False, label="Password",
        help_text="Required to technically validate or clinically verify.",
    )
    reason = forms.CharField(max_length=255, required=False, label="Reason / comment")

    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order
        self.result_fields: list[tuple[TestDefinition, forms.Field]] = []

        if order is None:
            return

        existing = {r.test_key: r for r in order.results.all()}
        for test in order.tests.all().order_by("code"):
            field_name = f"result_{test.id}"
            self.fields[field_name] = forms.CharField(
                required=False,
                label=f"{test.code} — {test.name}",
                initial=existing.get(test.id).value if test.id in existing else "",
            )
            self.result_fields.append((test, self[field_name]))

    def values(self) -> dict[str, str]:
        """Entered values keyed by test id, skipping blanks."""
        return {
            name.removeprefix("result_"): value
            for name, value in self.cleaned_data.items()
            if name.startswith("result_") and value not in (None, "")
        }


class SpecimenReceivingForm(forms.ModelForm):
    class Meta:
        model = SpecimenReceiving
        fields = [
            "specimen", "order", "received_by", "condition", "condition_notes",
            "rejection_reason", "temperature", "volume", "status",
        ]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == SpecimenReceiving.Status.REJECTED and not cleaned.get("rejection_reason"):
            raise forms.ValidationError(
                "A rejected specimen must record the rejection reason so the "
                "requester can be told why recollection is needed."
            )
        return cleaned


class PhlebotomyForm(forms.ModelForm):
    class Meta:
        model = PhlebotomySchedule
        fields = [
            "patient", "order", "ward_location", "scheduled_at", "collection_type",
            "tests", "assigned_to", "status", "notes",
        ]
        widgets = {"scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class QueueForm(forms.ModelForm):
    class Meta:
        model = AuthorizationQueue
        fields = ["name", "description", "department", "allowed_roles"]
        help_texts = {"allowed_roles": 'JSON list, e.g. ["manager", "scientist"]'}


class RetentionPolicyForm(forms.ModelForm):
    class Meta:
        model = RetentionPolicy
        fields = ["specimen_type", "retention_days", "temperature", "disposal_method", "notes", "active"]
