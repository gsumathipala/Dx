"""Session-level regulatory controls applied to every request."""
from __future__ import annotations

import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

#: Views whose response identifies one patient, for HIPAA access logging.
#:
#: Matched on the resolved view name rather than the URL, because path patterns
#: silently stop matching when a route moves. They did: these were written
#: against the Next.js URL scheme, so patient reports went unlogged after the
#: rewrite moved them to /reporting/reports/<pk>/.
#:
#: Each entry maps a view name to the URL keyword holding the identifier, and
#: how to resolve it to a patient.
PHI_VIEWS = {
    "patients:detail": ("pk", "patient"),
    "patients:trend": ("pk", "patient"),
    "patients:patient_update": ("pk", "patient"),
    "reporting:report_detail": ("pk", "order"),
    "reporting:amend": ("pk", "order"),
    "laboratory:result_entry": ("pk", "order"),
    "interop:fhir_report": ("pk", "order"),
    "interop:hl7_oru": ("pk", "order"),
}

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
                    # Release anything they left open before the session goes.
                    # An abandoned workstation must not hold a record hostage
                    # for the lock's full TTL on top of the idle timeout.
                    from apps.accounts.locking import release_all_for

                    release_all_for(user)
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

        patient = self._patient_for(request)
        if patient is None:
            return response

        self._log(request, user, patient)
        return response

    @staticmethod
    def _patient_for(request):
        """Resolve the patient this view discloses, if any."""
        from apps.patients.models import Patient

        match = request.resolver_match
        if match is None or match.view_name not in PHI_VIEWS:
            return None

        kwarg, kind = PHI_VIEWS[match.view_name]
        identifier = match.kwargs.get(kwarg)
        if identifier is None:
            return None

        if kind == "patient":
            return Patient.objects.filter(pk=identifier).only("id", "mrn").first()

        from apps.laboratory.models import Order

        order = (
            Order.objects.filter(pk=identifier)
            .select_related("patient")
            .only("id", "patient__id", "patient__mrn")
            .first()
        )
        return order.patient if order else None

    @staticmethod
    def _log(request, user, patient) -> None:
        from apps.compliance.models import PHIAccessLog

        PHIAccessLog.objects.create(
            user=user,
            username=user.username,
            patient=patient,
            patient_mrn=patient.mrn,
            path=request.path[:512],
            method=request.method,
            purpose=request.GET.get("purpose", "treatment"),
            ip_address=getattr(request, "_dx_client_ip", None),
            break_the_glass=request.session.pop("_dx_break_glass", False),
            justification=request.GET.get("justification"),
        )
