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


#: Workflow statuses and result flags, mapped to a visual tone.
#:
#: Result flags were missing from this map entirely, so every one of them fell
#: through to "muted" — a critical potassium rendered in the same grey as
#: "Draft", the lowest-salience style in the application. On the one screen
#: where somebody is deciding whether to telephone a ward, the flag was
#: de-emphasised.
BADGE_TONES = {
    # ── Workflow status ──────────────────────────────────────────────────────
    "Completed": "ok", "Clinically Verified": "ok", "Pass": "ok",
    "Active": "ok", "Accepted": "ok", "Sent": "ok", "Released": "ok",
    "Paid": "ok", "Closed": "ok", "Acceptable": "ok",
    "Pending": "warn", "In Progress": "warn", "Warning": "warn",
    "Resulted": "warn", "Technically Validated": "info", "Draft": "muted",
    "Scheduled": "muted", "Quarantine": "warn", "Marginal": "warn",
    "Failed": "danger", "Fail": "danger", "Rejected": "danger",
    "Cancelled": "danger", "Canceled": "danger", "Unacceptable": "danger",
    "Expired": "danger", "Escalated": "danger", "Open": "warn",
    # ── Result flags ─────────────────────────────────────────────────────────
    "Normal": "ok",
    "Low": "warn", "High": "warn", "Abnormal": "warn",
    "Critical Low": "critical", "Critical High": "critical",
}

#: A short marker shown alongside the text, so the meaning survives greyscale
#: printing and colour vision deficiency. WCAG 1.4.1 requires colour not to be
#: the only carrier; the clinical reason is the same one — roughly one man in
#: twelve cannot rely on it, and one of them is reading this at 3am.
BADGE_MARKERS = {
    "Low": "\u2193", "High": "\u2191",
    "Critical Low": "\u2193\u2193", "Critical High": "\u2191\u2191",
    "Abnormal": "!",
}


@register.filter
def status_badge(value: str) -> str:
    """Render a workflow status or result flag as a badge.

    The badge always carries the full text, plus a directional marker for
    result flags. Never colour alone.
    """
    tone = BADGE_TONES.get(value, "muted")
    marker = BADGE_MARKERS.get(value)
    if marker:
        return format_html(
            '<span class="badge badge-{}"><span aria-hidden="true">{}</span> {}</span>',
            tone, marker, value,
        )
    return format_html('<span class="badge badge-{}">{}</span>', tone, value)


#: Compact flag abbreviations, for dense grids where the full text will not
#: fit. These are the HL7 v2 Table 0078 abnormal-flag codes, which is what
#: `apps.interop.services.INTERPRETATION` already emits — so the screen and
#: the interchange say the same thing, and anybody who has read an HL7 message
#: recognises them.
FLAG_ABBREVIATIONS = {
    "Normal": "N", "Low": "L", "High": "H",
    "Critical Low": "LL", "Critical High": "HH", "Abnormal": "A",
}


@register.filter
def flag_badge(value: str) -> str:
    """A result flag in one or two characters, for a cumulative grid.

    The cumulative report previously kept only the first letter of the flag
    name in a uniform amber badge, which made "Critical High" and "Critical
    Low" both render as an identical "C" — the two results in the laboratory
    that must never be confused. Abbreviating to HH and LL distinguishes them,
    and the critical tone distinguishes both from a merely raised result.
    """
    abbreviation = FLAG_ABBREVIATIONS.get(value)
    if abbreviation is None:
        return format_html('<span class="badge badge-muted" title="{}">{}</span>',
                           value, value[:2])
    return format_html(
        '<span class="badge badge-{} badge-compact" title="{}">{}</span>',
        BADGE_TONES.get(value, "muted"), value, abbreviation,
    )


@register.filter
def dx_get(mapping, key):
    """Look up a dictionary by a key the template cannot express as a literal."""
    if hasattr(mapping, "get"):
        return mapping.get(key)
    return None
