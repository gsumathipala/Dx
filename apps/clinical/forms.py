"""Forms for configuring the clinical decision engine.

These screens edit the rules that decide what a result *means*, so the
validation here is doing real work rather than tidying input. Three patterns
recur:

* **Denormalised codes are filled in on save.** Several models keep a
  ``test_code`` alongside the foreign key so historic records still read
  correctly after a catalogue entry is renamed. The form is the only place
  that writes it, so it cannot drift.
* **Impossible configurations are refused, not warned about.** An inverted
  bound or a self-referential reflex silently never fires, or always does, and
  neither is visible from the screen afterwards.
* **The message says what to do.** Somebody configuring a delta rule at the end
  of a shift should not have to reason about why the form refused.
"""
from __future__ import annotations

from django import forms

from apps.clinical.models import (
    CalculatedTest, CriticalValueAcknowledgment, DeltaCheckRule,
    DemographicReferenceRange, NotifiableCondition, ReflexRule,
)


class DeltaCheckRuleForm(forms.ModelForm):
    class Meta:
        model = DeltaCheckRule
        fields = ["test", "delta_type", "threshold", "direction", "lookback_days", "enabled"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("test"):
            cleaned["test_code"] = cleaned["test"].code
        threshold = cleaned.get("threshold")
        # Zero would flag every result including an identical one, and a
        # negative threshold can never be exceeded, so the rule would be dead.
        if threshold is not None and threshold <= 0:
            raise forms.ValidationError("The threshold must be greater than zero.")
        return cleaned

    def save(self, commit=True):
        # test_code is denormalised so the rule still reads correctly after the
        # catalogue entry is renamed; this form is the only writer.
        rule = super().save(commit=False)
        rule.test_code = rule.test.code
        if commit:
            rule.save()
        return rule


class ReflexRuleForm(forms.ModelForm):
    class Meta:
        model = ReflexRule
        fields = ["name", "trigger_test", "operator", "threshold", "add_test", "enabled"]

    def clean(self):
        cleaned = super().clean()
        trigger, added = cleaned.get("trigger_test"), cleaned.get("add_test")
        if trigger and added and trigger == added:
            raise forms.ValidationError(
                "A reflex rule cannot add the test that triggered it — that would loop."
            )
        return cleaned

    def save(self, commit=True):
        rule = super().save(commit=False)
        rule.add_test_code = rule.add_test.code
        if commit:
            rule.save()
        return rule


class DemographicRangeForm(forms.ModelForm):
    class Meta:
        model = DemographicReferenceRange
        fields = [
            "test", "age_min", "age_max", "gender", "pregnancy", "trimester",
            "low_normal", "high_normal", "low_critical", "high_critical",
            "unit", "notes", "active",
        ]

    def clean(self):
        cleaned = super().clean()
        age_min, age_max = cleaned.get("age_min"), cleaned.get("age_max")
        if age_min is not None and age_max is not None and age_min > age_max:
            raise forms.ValidationError("The minimum age cannot exceed the maximum age.")

        low, high = cleaned.get("low_normal"), cleaned.get("high_normal")
        if low is not None and high is not None and low > high:
            raise forms.ValidationError("The lower reference bound cannot exceed the upper bound.")

        # A critical limit inside the reference interval means every normal
        # result is also critical. The engine would do exactly as told and the
        # laboratory would telephone the ward about healthy patients.
        low_critical, high_critical = cleaned.get("low_critical"), cleaned.get("high_critical")
        if low_critical is not None and low is not None and low_critical > low:
            raise forms.ValidationError(
                "The critically-low limit must be at or below the lower reference bound."
            )
        if high_critical is not None and high is not None and high_critical < high:
            raise forms.ValidationError(
                "The critically-high limit must be at or above the upper reference bound."
            )
        if cleaned.get("trimester") and not cleaned.get("pregnancy"):
            raise forms.ValidationError("A trimester only applies to a pregnancy-specific interval.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.test_code = obj.test.code
        if commit:
            obj.save()
        return obj


class CalculatedTestForm(forms.ModelForm):
    class Meta:
        model = CalculatedTest
        fields = ["test_code", "name", "formula", "inputs", "unit", "active"]
        help_texts = {"inputs": 'JSON list of input test codes, e.g. ["TC", "HDL", "TG"]'}


class NotifiableConditionForm(forms.ModelForm):
    class Meta:
        model = NotifiableCondition
        fields = ["name", "organism", "tests", "reporting_body", "timeframe", "active"]


class CriticalAcknowledgementForm(forms.ModelForm):
    """Documented read-back of a critical value (CAP GEN.41320)."""

    class Meta:
        model = CriticalValueAcknowledgment
        fields = [
            "notified_clinician", "notification_method", "read_back_confirmed",
            "notes", "escalated_to",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("read_back_confirmed"):
            raise forms.ValidationError(
                "Confirm that the recipient repeated the result back. Read-back is "
                "required evidence that the critical value was communicated correctly."
            )
        if not cleaned.get("notified_clinician"):
            raise forms.ValidationError("Record who was notified.")
        return cleaned
