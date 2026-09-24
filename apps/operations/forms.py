"""Forms for the operational configuration screens.

Mostly thin wrappers over their models. The ones with real logic are the
turnaround thresholds, where the warning time must sit between the target and
the breach or the escalation never fires, and storage assignment, which must
not place two specimens in one position.
"""
from __future__ import annotations

from django import forms

from apps.operations.models import (
    Feedback, Message, RoutingRule, StorageAssignment, StorageLocation,
    SystemAlert, SystemSetting, TatThreshold, Worksheet, Workstation,
)


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["recipient", "recipient_department", "subject", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("recipient") and not cleaned.get("recipient_department"):
            raise forms.ValidationError("Choose a recipient or a department.")
        return cleaned


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["type", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}


class SystemAlertForm(forms.ModelForm):
    class Meta:
        model = SystemAlert
        fields = ["message", "type", "expires_at", "active"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 2}),
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = ["key", "value", "description"]


class WorksheetForm(forms.ModelForm):
    class Meta:
        model = Worksheet
        fields = ["name", "department", "tests", "orders", "status"]


class WorkstationForm(forms.ModelForm):
    class Meta:
        model = Workstation
        fields = [
            "name", "department", "ip_address", "printer_id", "instruments",
            "supported_tests", "supported_specimen_types", "status",
            "max_throughput", "active",
        ]


class RoutingRuleForm(forms.ModelForm):
    class Meta:
        model = RoutingRule
        fields = ["test", "workstations", "department", "specimen_type", "conditions", "priority", "active"]


class TatThresholdForm(forms.ModelForm):
    class Meta:
        model = TatThreshold
        fields = ["scope", "test", "department", "target_hours", "warning_hours", "breach_hours", "priority", "active"]

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get("scope")
        if scope == TatThreshold.Scope.TEST and not cleaned.get("test"):
            raise forms.ValidationError("A test-scoped threshold must name a test.")
        if scope == TatThreshold.Scope.DEPARTMENT and not cleaned.get("department"):
            raise forms.ValidationError("A department-scoped threshold must name a department.")

        target = cleaned.get("target_hours")
        warning = cleaned.get("warning_hours")
        breach = cleaned.get("breach_hours")
        if None not in (target, warning, breach) and not warning <= target <= breach:
            raise forms.ValidationError(
                "The thresholds must read warning ≤ target ≤ breach, so a warning "
                "is raised before the target is missed."
            )
        return cleaned


class StorageLocationForm(forms.ModelForm):
    class Meta:
        model = StorageLocation
        fields = ["name", "kind", "parent", "temperature", "capacity", "rows", "columns", "active"]


class StorageAssignmentForm(forms.ModelForm):
    class Meta:
        model = StorageAssignment
        fields = ["specimen", "location", "position"]

    def clean(self):
        cleaned = super().clean()
        location, position = cleaned.get("location"), cleaned.get("position")
        if location and location.is_full:
            raise forms.ValidationError(f"{location.name} is at capacity.")
        if location and position:
            clash = StorageAssignment.objects.filter(
                location=location, position=position, removed_at__isnull=True
            ).exclude(pk=self.instance.pk)
            if clash.exists():
                raise forms.ValidationError(f"Position {position} in {location.name} is already occupied.")
        return cleaned
