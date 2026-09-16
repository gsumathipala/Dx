"""Enrolling, challenging and disabling the second factor."""
from __future__ import annotations

import time

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts import mfa

User = get_user_model()

#: How long a half-finished sign-in may sit between password and code.
CHALLENGE_TTL_SECONDS = 300
#: Failed codes before the half-finished sign-in is thrown away entirely.
CHALLENGE_ATTEMPTS = 5

PENDING_USER = "_dx_mfa_pending"
PENDING_SINCE = "_dx_mfa_since"
PENDING_TRIES = "_dx_mfa_tries"


class CodeForm(forms.Form):
    code = forms.CharField(
        label="Code from your authenticator",
        max_length=32,
        widget=forms.TextInput(attrs={
            "autocomplete": "one-time-code", "inputmode": "numeric",
            "autofocus": "autofocus", "placeholder": "000000",
        }),
        help_text="Or one of your recovery codes if you no longer have the device.",
    )


class DisableForm(forms.Form):
    password = forms.CharField(label="Your password", widget=forms.PasswordInput)
    code = forms.CharField(label="A current code from your authenticator", max_length=32)


# ── Challenge, between password and session ──────────────────────────────────


def begin_challenge(request, user) -> None:
    request.session[PENDING_USER] = str(user.pk)
    request.session[PENDING_SINCE] = time.time()
    request.session[PENDING_TRIES] = 0


def _clear(request) -> None:
    for key in (PENDING_USER, PENDING_SINCE, PENDING_TRIES):
        request.session.pop(key, None)


def _pending_user(request):
    user_id = request.session.get(PENDING_USER)
    started = request.session.get(PENDING_SINCE)
    if not user_id or not started:
        return None
    if time.time() - float(started) > CHALLENGE_TTL_SECONDS:
        _clear(request)
        return None
    return User.objects.filter(pk=user_id, is_active=True).first()


def challenge(request):
    """The second step of signing in.

    The user is authenticated by password at this point but has **no session**:
    ``login()`` has not been called, so nothing in the application treats them
    as signed in. That matters — a half-finished sign-in that already carried
    a session would be a first factor dressed up as two.
    """
    user = _pending_user(request)
    if user is None:
        messages.error(request, "That sign-in timed out. Start again.")
        return redirect("accounts:login")

    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        presented = form.cleaned_data["code"]
        device = mfa.device_for(user)

        accepted = bool(device and device.verify(presented))
        used_recovery = False
        if not accepted:
            used_recovery = mfa.consume_recovery_code(user, presented)
            accepted = used_recovery

        if accepted:
            _clear(request)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            if used_recovery:
                left = mfa.unused_recovery_code_count(user)
                messages.warning(
                    request,
                    f"You signed in with a recovery code. {left} remain. "
                    "Set up your authenticator again and generate a fresh set.",
                )
            return redirect(request.GET.get("next") or "operations:dashboard")

        tries = int(request.session.get(PENDING_TRIES, 0)) + 1
        request.session[PENDING_TRIES] = tries
        if tries >= CHALLENGE_ATTEMPTS:
            _clear(request)
            messages.error(
                request, "Too many incorrect codes. Sign in again from the start."
            )
            return redirect("accounts:login")
        messages.error(request, "That code was not accepted.")

    return render(request, "accounts/mfa_challenge.html", {
        "form": form,
        "username": user.username,
        "recovery_codes_left": mfa.unused_recovery_code_count(user),
    })


# ── Enrolment ────────────────────────────────────────────────────────────────


def setup(request):
    """Bind an authenticator to this account.

    A device is created unconfirmed and stays that way until the user produces
    a code from it. An unconfirmed device never gates a login — locking
    somebody out with a secret they failed to scan is the classic way to make
    a laboratory turn MFA off.
    """
    device, created = mfa.MfaDevice.objects.get_or_create(
        user=request.user,
        defaults={"sealed_secret": mfa.seal(mfa.generate_secret())},
    )
    if device.is_confirmed:
        return redirect("accounts:mfa_status")

    if not created and request.GET.get("reset"):
        device.sealed_secret = mfa.seal(mfa.generate_secret())
        device.save(update_fields=["sealed_secret"])

    secret = device.secret
    form = CodeForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        if mfa.verify_code(secret, form.cleaned_data["code"]) is not None:
            from django.utils import timezone

            device.confirmed_at = timezone.now()
            device.save(update_fields=["confirmed_at"])
            codes = mfa.issue_recovery_codes(request.user)

            _record("mfa enrolled", request.user)
            return render(request, "accounts/mfa_recovery_codes.html", {
                "codes": codes, "first_time": True,
            })
        messages.error(request, "That code was not accepted. Check your device's clock.")

    return render(request, "accounts/mfa_setup.html", {
        "form": form,
        "secret": secret,
        "grouped_secret": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)),
        "uri": mfa.provisioning_uri(secret, username=request.user.username),
        "required": mfa.is_required_for(request.user),
    })


def status(request):
    return render(request, "accounts/mfa_status.html", {
        "state": mfa.state_for(request.user),
    })


@require_POST
def regenerate_recovery_codes(request):
    if mfa.device_for(request.user) is None:
        messages.error(request, "Set up an authenticator first.")
        return redirect("accounts:mfa_status")

    codes = mfa.issue_recovery_codes(request.user)
    _record("mfa recovery codes regenerated", request.user)
    return render(request, "accounts/mfa_recovery_codes.html", {
        "codes": codes, "first_time": False,
    })


def disable(request):
    """Remove the second factor. Requires the password *and* a current code.

    Requiring both means somebody who has stolen a session cannot quietly turn
    the control off — which would otherwise be the first thing they did.
    """
    if mfa.is_required_for(request.user):
        messages.error(
            request,
            "A second factor is mandatory for your role and cannot be removed. "
            "If you have lost your device, use a recovery code and enrol again.",
        )
        return redirect("accounts:mfa_status")

    device = mfa.device_for(request.user)
    if device is None:
        return redirect("accounts:mfa_status")

    form = DisableForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not request.user.check_password(form.cleaned_data["password"]):
            messages.error(request, "That password was not accepted.")
        elif not device.verify(form.cleaned_data["code"]):
            messages.error(request, "That code was not accepted.")
        else:
            device.delete()
            mfa.MfaRecoveryCode.objects.filter(user=request.user).delete()
            _record("mfa disabled", request.user)
            messages.warning(
                request,
                "Two-factor authentication is off for your account. Your "
                "password is now the only thing protecting it.",
            )
            return redirect("accounts:mfa_status")

    return render(request, "accounts/mfa_disable.html", {"form": form})


def _record(label: str, user) -> None:
    from apps.audit.recorder import record
    from apps.common.constants import AuditAction

    record(
        action=AuditAction.UPDATE,
        entity_type="accounts.User",
        entity_id=user.pk,
        entity_label=f"{label}: {user.username}",
        blocking=True,
    )
