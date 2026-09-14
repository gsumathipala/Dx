from __future__ import annotations

from django import forms

from apps.quality.models import (
    Equipment, EquipmentLog, QcDefinition, QcMaterial, QcRun, RejectionCriterion,
)


class QcRunForm(forms.ModelForm):
    """Entering a control value. Westgard evaluation happens on save."""

    class Meta:
        model = QcRun
        fields = ["definition", "value", "performed_by", "instrument", "comments"]
        widgets = {"comments": forms.Textarea(attrs={"rows": 2})}


class QcMaterialForm(forms.ModelForm):
    class Meta:
        model = QcMaterial
        fields = ["name", "lot_number", "expiration_date", "manufacturer", "level", "active"]
        widgets = {"expiration_date": forms.DateInput(attrs={"type": "date"})}


class QcDefinitionForm(forms.ModelForm):
    class Meta:
        model = QcDefinition
        fields = ["material", "test", "mean", "sd", "unit"]

    def clean_sd(self):
        sd = self.cleaned_data["sd"]
        if sd <= 0:
            raise forms.ValidationError(
                "The standard deviation must be greater than zero — Westgard rules "
                "cannot be evaluated without it."
            )
        return sd

    def save(self, commit=True):
        definition = super().save(commit=False)
        definition.test_code = definition.test.code
        definition.test_name = definition.test.name
        if commit:
            definition.save()
        return definition


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            "name", "type", "serial_number", "manufacturer", "department", "status",
            "last_service_date", "next_service_date",
            "last_calibration_date", "next_calibration_date", "active",
        ]
        widgets = {
            field: forms.DateInput(attrs={"type": "date"})
            for field in ("last_service_date", "next_service_date",
                          "last_calibration_date", "next_calibration_date")
        }


class EquipmentLogForm(forms.ModelForm):
    class Meta:
        model = EquipmentLog
        fields = ["equipment", "type", "description", "performed_by", "outcome"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class RejectionCriterionForm(forms.ModelForm):
    class Meta:
        model = RejectionCriterion
        fields = ["reason", "description", "category", "active"]
