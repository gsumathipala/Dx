"""Template context for compliance status indicators."""
from __future__ import annotations

from django.conf import settings
from django.utils import timezone


def compliance_banner(request):
    """Surface anything that needs the user's attention on every page.

    Kept deliberately cheap: a laboratory user should see an unacknowledged
    integrity alert or an overdue competency without a per-page cost that makes
    the UI sluggish.
    """
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}

    from apps.audit.verification import open_alerts
    from apps.compliance.services import security_state

    context = {"dx_integrity_alerts": 0, "dx_password_expires_in": None}

    if user.is_manager:
        context["dx_integrity_alerts"] = open_alerts().count()

    state = security_state(user)
    expiry = state.password_expires_at
    if expiry:
        remaining = (expiry - timezone.now()).days
        if remaining <= 14:
            context["dx_password_expires_in"] = max(remaining, 0)

    context["dx_controls"] = {
        "qc_lockout": getattr(settings, "ENFORCE_QC_LOCKOUT", True),
        "competency_gating": getattr(settings, "ENFORCE_COMPETENCY_GATING", True),
        "self_verification_block": getattr(settings, "ENFORCE_SELF_VERIFICATION_BLOCK", True),
        "signature_reauth": getattr(settings, "REQUIRE_REAUTH_FOR_SIGNATURE", True),
    }
    return context
