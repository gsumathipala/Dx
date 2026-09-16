"""The two endpoints single sign-on needs: start, and come back."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from apps.accounts import mfa, sso

logger = logging.getLogger("dx.sso")


def begin(request):
    """Send the browser to the identity provider."""
    if not sso.is_enabled():
        messages.error(request, "Single sign-on is not configured on this system.")
        return redirect("accounts:login")

    try:
        destination = sso.begin(request, next_url=request.GET.get("next", ""))
    except sso.SsoError as error:
        logger.warning("Could not start SSO: %s", error)
        messages.error(request, str(error))
        return redirect("accounts:login")
    return redirect(destination)


def callback(request):
    """Come back from the identity provider with an authorization code."""
    from apps.audit.recorder import record
    from apps.common.constants import AuditAction

    if request.GET.get("error"):
        # The provider refused. Its own description is more useful than ours.
        detail = request.GET.get("error_description") or request.GET["error"]
        messages.error(request, f"Single sign-on was refused: {detail}")
        return redirect("accounts:login")

    code, state = request.GET.get("code"), request.GET.get("state")
    if not code:
        messages.error(request, "The identity provider returned no authorization code.")
        return redirect("accounts:login")

    try:
        claims = sso.exchange(request, code=code, state=state)
        user, created = sso.resolve_user(claims)
    except sso.SsoError as error:
        logger.warning("SSO sign-in refused: %s", error)
        messages.error(request, str(error))
        return redirect("accounts:login")

    # A second factor is still a second factor. If the identity provider
    # asserts one was used (the `amr` claim), accept it; otherwise challenge
    # here, because "SSO is enabled" is not the same as "MFA was performed".
    provider_did_mfa = "mfa" in (claims.get("amr") or [])
    if not provider_did_mfa and (mfa.device_for(user) or mfa.is_required_for(user)):
        from apps.accounts.mfa_views import begin_challenge

        begin_challenge(request, user)
        return redirect("accounts:mfa_challenge")

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    record(
        action=AuditAction.LOGIN,
        entity_type="accounts.User",
        entity_id=user.pk,
        entity_label=(
            f"signed in through {sso.provider_name()}"
            + (" (account provisioned)" if created else "")
        ),
        blocking=True,
    )
    if created:
        messages.info(
            request,
            f"An account was created for you with the {user.get_role_display()} "
            "role. Ask an administrator if that is not right.",
        )
    return redirect(request.session.pop("_dx_sso_next", None) or "operations:dashboard")
