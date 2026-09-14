"""Session-level regulatory controls applied to every request."""
from __future__ import annotations

import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

#: Paths that identify a patient record being viewed, for PHI access logging.
PHI_PATH_PATTERNS = [
    re.compile(r"^/patients/(?P<pk>[^/]+)/"),
    re.compile(r"^/patient-360/(?P<pk>[^/]+)/"),
    re.compile(r"^/reports/(?P<pk>[^/]+)/"),
]

EXEMPT_PREFIXES = ("/static/", "/media/", "/accounts/login", "/accounts/logout", "/healthz")


class RegulatorySessionMiddleware:
    """Enforces auto-logoff, password expiry and forced password change.

    21 CFR Part 11 §11.10(d) expects system access to be limited to authorised
    individuals; an unattended authenticated workstation defeats that, so idle
    sessions are terminated.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.idle_limit = getattr(settings, "IDLE_TIMEOUT_MINUTES", 20) * 60

    def __call__(self, request):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated) or request.path.startswith(EXEMPT_PREFIXES):
            return self.get_response(request)

        now = timezone.now()

        # ── Idle auto-logoff ─────────────────────────────────────────────────
        if self.idle_limit:
            last_seen = request.session.get("_dx_last_seen")
            if last_seen:
                idle_for = now.timestamp() - float(last_seen)
                if idle_for > self.idle_limit:
                    logout(request)
                    messages.warning(
                        request,
                        f"You were signed out after {self.idle_limit // 60} minutes of inactivity.",
                    )
                    return redirect(settings.LOGIN_URL)
            request.session["_dx_last_seen"] = now.timestamp()

        # ── Password ageing ──────────────────────────────────────────────────
        change_url = reverse("compliance:password_change")
        if request.path != change_url:
            from apps.compliance.services import security_state

            state = security_state(user)
            if state.must_change_password or state.password_expired:
                messages.warning(request, "Your password must be changed before you continue.")
                return redirect(change_url)

        return self.get_response(request)


class PHIAccessLogMiddleware:
    """Records views of identifiable patient information (HIPAA §164.312(b))."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.audit.context import client_ip

        request._dx_client_ip = client_ip(request)
        response = self.get_response(request)

        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return response
        if request.method != "GET" or response.status_code >= 400:
            return response

        patient_pk = self._patient_from_path(request.path)
        if patient_pk is None:
            return response

        self._log(request, user, patient_pk)
        return response

    @staticmethod
    def _patient_from_path(path: str) -> str | None:
        for pattern in PHI_PATH_PATTERNS:
            match = pattern.match(path)
            if match:
                return match.group("pk")
        return None

    @staticmethod
    def _log(request, user, patient_pk: str) -> None:
        from apps.compliance.models import PHIAccessLog
        from apps.patients.models import Patient

        patient = Patient.objects.filter(pk=patient_pk).only("id", "mrn").first()
        PHIAccessLog.objects.create(
            user=user,
            username=user.username,
            patient=patient,
            patient_mrn=patient.mrn if patient else "",
            path=request.path[:512],
            method=request.method,
            purpose=request.GET.get("purpose", "treatment"),
            ip_address=getattr(request, "_dx_client_ip", None),
            break_the_glass=request.session.pop("_dx_break_glass", False),
            justification=request.GET.get("justification"),
        )
