"""Forms for authentication and user administration."""
from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from apps.accounts.models import Department, UserCompetency
from apps.common.constants import Role

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
    """Create or edit an account.

    Passwords are not set here. A new account is given a temporary password by
    the administrator on the separate reset screen, which forces a change at
    first sign-in — so no administrator ever knows a colleague's working
    password, and every reset is a distinct, auditable act.
    """

    class Meta:
        model = User
        fields = ["username", "name", "role", "department", "email", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The installer account is created by `manage.py create_installer` and
        # is a singleton; it must not be conjured or converted through the UI.
        self.fields["role"].choices = [
            (value, label) for value, label in self.fields["role"].choices
            if value != Role.INSTALLER
        ]
        if self.instance.pk and self.instance.is_protected_account:
            for name in ("username", "role"):
                self.fields[name].disabled = True
            self.fields["role"].help_text = (
                "The installer role is fixed for this account."
            )

    def clean_role(self):
        role = self.cleaned_data["role"]
        if self.instance.pk and self.instance.is_protected_account:
            return self.instance.role
        if role == Role.INSTALLER:
            raise forms.ValidationError(
                "The installer account cannot be created from here. It is a single "
                "permanent account created with `manage.py create_installer`."
            )
        return role


class AdminPasswordResetForm(forms.Form):
    """Issue a temporary password that the holder must change at first use."""

    new_password = forms.CharField(widget=forms.PasswordInput, label="Temporary password")
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    reason = forms.CharField(
        max_length=255,
        help_text="Recorded in the audit trail — for example 'forgotten password, "
                  "identity confirmed in person'.",
    )

    def __init__(self, target, *args, **kwargs):
        self.target = target
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        new, confirm = cleaned.get("new_password"), cleaned.get("confirm_password")
        if new and confirm and new != confirm:
            raise forms.ValidationError("The passwords do not match.")
        if new:
            password_validation.validate_password(new, self.target)
        return cleaned


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
