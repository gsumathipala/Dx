from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.patients.models import Patient


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["first_name", "last_name", "dob", "gender", "mrn", "email", "phone", "address"]
        widgets = {
            "dob": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_dob(self):
        dob = self.cleaned_data["dob"]
        if dob > timezone.localdate():
            raise forms.ValidationError("A date of birth cannot be in the future.")
        return dob
