"""Forms for the rule builder.

Conditions and actions are edited as inline formsets on the rule's own form, so
a rule is written, read and saved as one thing. Splitting them over three
screens would make it possible to save a rule whose conditions were never
finished — which is exactly the rule that quietly matches everything.
"""
from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from apps.rules.models import Rule, RuleAction, RuleCondition


class RuleForm(forms.ModelForm):
    class Meta:
        model = Rule
        fields = [
            "name", "description", "trigger", "test", "department",
            "priority", "stop_on_match", "active", "change_control",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "active": "A disabled rule is never evaluated, whatever its approval state.",
        }

    def clean(self):
        cleaned = super().clean()
        return cleaned


class RuleConditionForm(forms.ModelForm):
    class Meta:
        model = RuleCondition
        fields = ["group", "subject", "operator", "value", "value_to"]

    def clean(self):
        cleaned = super().clean()
        operator = cleaned.get("operator")
        value = (cleaned.get("value") or "").strip()
        value_to = (cleaned.get("value_to") or "").strip()

        if operator in RuleCondition.UNARY:
            return cleaned
        if not value:
            raise forms.ValidationError("This comparison needs a value.")
        if operator in RuleCondition.BINARY and not value_to:
            raise forms.ValidationError("'is between' needs both bounds.")

        subject = cleaned.get("subject")
        if subject in RuleCondition.NUMERIC_SUBJECTS and operator not in (
            RuleCondition.Operator.IN, RuleCondition.Operator.NOT_IN
        ):
            for candidate in filter(None, [value, value_to]):
                try:
                    float(candidate)
                except ValueError:
                    raise forms.ValidationError(
                        f"{dict(RuleCondition.Subject.choices)[subject]} is numeric, "
                        f"so {candidate!r} cannot be compared against it."
                    )
        return cleaned


class RuleActionForm(forms.ModelForm):
    class Meta:
        model = RuleAction
        fields = ["kind", "text", "flag", "add_test", "recipient_role", "severity"]
        widgets = {"text": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")

        if kind == RuleAction.Kind.APPEND_COMMENT and not (cleaned.get("text") or "").strip():
            raise forms.ValidationError("An interpretive comment needs some text.")
        if kind == RuleAction.Kind.SET_FLAG and not (cleaned.get("flag") or "").strip():
            raise forms.ValidationError("Say which flag to add.")
        if kind == RuleAction.Kind.ADD_TEST and not cleaned.get("add_test"):
            raise forms.ValidationError("Say which test to add.")
        if kind == RuleAction.Kind.NOTIFY and not (cleaned.get("recipient_role") or "").strip():
            raise forms.ValidationError("Say which role should be told.")
        return cleaned


ConditionFormSet = inlineformset_factory(
    Rule, RuleCondition, form=RuleConditionForm, extra=3, can_delete=True
)
ActionFormSet = inlineformset_factory(
    Rule, RuleAction, form=RuleActionForm, extra=2, can_delete=True
)


class RuleApprovalForm(forms.Form):
    """Approving a rule is an electronic signature, so it re-authenticates."""

    comment = forms.CharField(
        label="What was reviewed",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=(
            "How this rule was validated — the cases it was tested against, "
            "and who reviewed it. This is the record an inspector reads."
        ),
    )
    password = forms.CharField(
        label="Your password", widget=forms.PasswordInput, required=False,
        help_text="Required to sign the approval.",
    )


class OverrideForm(forms.Form):
    reason = forms.CharField(
        label="Why are you taking this back?",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=(
            "The result returns to the worklist for a person to verify. "
            "This reason is recorded against the automatic release."
        ),
    )


class SimulationForm(forms.Form):
    """Try a rule against a real historic result before approving it."""

    accession_number = forms.CharField(
        label="Accession number",
        help_text="An order whose results should be run past this rule.",
    )
    test_code = forms.CharField(
        label="Test code", required=False,
        help_text="Leave blank to try every result on the order.",
    )
