"""Template helpers used by the generic list and form templates."""
from __future__ import annotations

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def dx_attr(obj, path: str):
    """Resolve a dotted attribute path, calling it if it is a method.

    ``{{ order|dx_attr:"patient.full_name" }}`` keeps the generic list template
    free of per-model markup.
    """
    value = obj
    for part in path.split("."):
        if value is None:
            return ""
        value = getattr(value, part, None)
        if callable(value):
            value = value()
    if value is None:
        return "—"
    if value is True:
        return mark_safe('<span class="badge badge-ok">Yes</span>')
    if value is False:
        return mark_safe('<span class="badge badge-muted">No</span>')
    return value


@register.filter
def dx_label(obj) -> str:
    """The ``app_label.ModelName`` of an instance, for audit history links."""
    return obj._meta.label


@register.filter
def status_badge(value: str) -> str:
    """Colour a workflow status consistently across screens."""
    mapping = {
        "Completed": "ok", "Clinically Verified": "ok", "Pass": "ok",
        "Active": "ok", "Accepted": "ok", "Sent": "ok", "Released": "ok",
        "Paid": "ok", "Closed": "ok", "Acceptable": "ok",
        "Pending": "warn", "In Progress": "warn", "Warning": "warn",
        "Resulted": "warn", "Technically Validated": "info", "Draft": "muted",
        "Scheduled": "muted", "Quarantine": "warn", "Marginal": "warn",
        "Failed": "danger", "Fail": "danger", "Rejected": "danger",
        "Cancelled": "danger", "Canceled": "danger", "Unacceptable": "danger",
        "Expired": "danger", "Escalated": "danger", "Open": "warn",
    }
    tone = mapping.get(value, "muted")
    return format_html('<span class="badge badge-{}">{}</span>', tone, value)


@register.filter
def dx_get(mapping, key):
    """Look up a dictionary by a key the template cannot express as a literal."""
    if hasattr(mapping, "get"):
        return mapping.get(key)
    return None
