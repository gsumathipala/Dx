"""Forms for authentication and user administration."""
from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

from apps.accounts.models import Department, UserCompetency

User = get_user_model()


class DxLoginForm(AuthenticationForm):
    """Login form that explains a lockout rather than a generic failure."""

    def confirm_login_allowed(self, user):
        from apps.compliance.services import check_account_available

        check = check_account_available(user)
        if not check.allowed:
            raise forms.ValidationError(check.message, code="locked")
        super().confirm_login_allowed(user)


class UserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput, required=False,
        help_text="Leave blank to keep the current password.",
    )

    class Meta:
        model = User
        fields = ["username", "name", "role", "department", "email", "is_active"]

    def save(self, commit=True):
        user = super().save(commit=False)
        raw = self.cleaned_data.get("password")
        if raw:
            user.set_password(raw)
        if commit:
            user.save()
            if raw:
                from apps.compliance.services import record_password_change

                record_password_change(user)
        return user


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "code", "type", "description", "enabled"]


class CompetencyForm(forms.ModelForm):
    class Meta:
        model = UserCompetency
        fields = [
            "user", "test", "category", "competency_date", "expiry_date",
            "assessed_by", "status", "notes",
        ]
        widgets = {
            "competency_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("test") and not cleaned.get("category"):
            raise forms.ValidationError(
                "Specify either a test or a discipline category — a competency "
                "record that covers nothing cannot gate anything."
            )
        competency_date, expiry = cleaned.get("competency_date"), cleaned.get("expiry_date")
        if competency_date and expiry and expiry <= competency_date:
            raise forms.ValidationError("The expiry date must be after the assessment date.")
        return cleaned
