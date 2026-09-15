"""Enforcement of the regulatory controls.

These functions are the gate the workflow calls before it lets a user do
something a regulator cares about. Each raises ``ControlViolation`` with a
message suitable for display, so callers do not have to interpret result codes.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.audit.hashing import canonical_json
from apps.audit.recorder import record
from apps.common.constants import AuditAction
from apps.compliance.models import (
    AccountSecurityState,
    CorrectiveAction,
    ElectronicSignature,
    PasswordHistory,
)


class ControlViolation(PermissionDenied):
    """A regulatory control blocked the requested action."""

    def __init__(self, message: str, citation: str = ""):
        super().__init__(message)
        self.message = message
        self.citation = citation

    def __str__(self) -> str:
        return f"{self.message} [{self.citation}]" if self.citation else self.message


@dataclass
class ControlCheck:
    allowed: bool
    message: str = ""
    citation: str = ""

    def enforce(self) -> None:
        if not self.allowed:
            raise ControlViolation(self.message, self.citation)


# ── CLIA §493.1451: competency gating ────────────────────────────────────────


def check_competency(user, test) -> ControlCheck:
    """Confirm the user holds current competency for the test or its discipline.

    CLIA requires competency assessment before staff report patient results,
    semi-annually in the first year and annually thereafter.
    """
    if not getattr(settings, "ENFORCE_COMPETENCY_GATING", True):
        return ControlCheck(True)
    if user.is_admin:
        return ControlCheck(True)

    from apps.accounts.models import UserCompetency

    today = timezone.localdate()
    records = UserCompetency.objects.filter(
        user=user,
        status=UserCompetency.Status.ACTIVE,
        expiry_date__gte=today,
    )
    if test is not None:
        department_id = getattr(test, "department_id", None)
        matches = records.filter(test=test)
        if department_id and not matches.exists():
            # A discipline-wide competency covers every test in that department.
            matches = records.filter(test__isnull=True, category__iexact=str(test.department))
        if matches.exists():
            return ControlCheck(True)
    elif records.exists():
        return ControlCheck(True)

    return ControlCheck(
        False,
        f"{user.get_full_name()} has no current competency record for "
        f"{getattr(test, 'code', 'this test')}. Reporting is blocked until competency is assessed.",
        "CLIA 42 CFR §493.1451(b)(8)",
    )


# ── CLIA self-review: the entering analyst may not verify their own work ─────


def check_self_verification(user, result) -> ControlCheck:
    if not getattr(settings, "ENFORCE_SELF_VERIFICATION_BLOCK", True):
        return ControlCheck(True)
    if result.entered_by and result.entered_by == user.username:
        return ControlCheck(
            False,
            "You entered this result and cannot also verify it. "
            "A second qualified person must perform verification.",
            "CLIA 42 CFR §493.1495 (independent review)",
        )
    return ControlCheck(True)


# ── CLIA §493.1256: QC lockout ───────────────────────────────────────────────


def check_qc_status(test, *, at=None) -> ControlCheck:
    """Block release when the most recent QC for the test failed.

    CLIA requires QC to be acceptable before patient results are reported; a
    failed run must be investigated and repeated first.
    """
    if not getattr(settings, "ENFORCE_QC_LOCKOUT", True) or test is None:
        return ControlCheck(True)

    from apps.quality.models import QcRun

    at = at or timezone.now()
    window_start = at - timedelta(hours=24)
    latest = (
        QcRun.objects.filter(
            definition__test_code=test.code,
            timestamp__gte=window_start,
            timestamp__lte=at,
        )
        .order_by("-timestamp")
        .first()
    )

    if latest is None:
        return ControlCheck(
            False,
            f"No quality control has been run for {test.code} in the last 24 hours. "
            "Patient results cannot be released without acceptable QC.",
            "CLIA 42 CFR §493.1256(d)",
        )
    if latest.status == QcRun.Status.FAIL:
        return ControlCheck(
            False,
            f"The most recent QC run for {test.code} failed "
            f"({', '.join(latest.result_flags or []) or 'out of range'}). "
            "Investigate and repeat QC before releasing patient results.",
            "CLIA 42 CFR §493.1256(d)(3)",
        )
    return ControlCheck(True)


# ── 21 CFR Part 11 §11.200: electronic signature ─────────────────────────────


def content_hash(payload: dict) -> str:
    """SHA-256 of the content being signed, binding signature to record."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@transaction.atomic
def apply_signature(
    *,
    user,
    meaning: str,
    entity_type: str,
    entity_id: str,
    payload: dict,
    password: str | None = None,
    comment: str | None = None,
    request=None,
) -> ElectronicSignature:
    """Create a Part 11 electronic signature, re-authenticating the signer.

    §11.200(a)(1) requires a signature applied by someone already in session to
    use at least one component — here the password — at the moment of signing.
    """
    require_reauth = getattr(settings, "REQUIRE_REAUTH_FOR_SIGNATURE", True)
    reauthenticated = False

    if require_reauth:
        if not password:
            raise ControlViolation(
                "Your password is required to apply an electronic signature.",
                "21 CFR Part 11 §11.200(a)(1)",
            )
        verified = authenticate(request, username=user.username, password=password)
        if verified is None or verified.pk != user.pk:
            raise ControlViolation(
                "Password verification failed — signature not applied.",
                "21 CFR Part 11 §11.200(a)(1)",
            )
        reauthenticated = True

    digest = content_hash(payload)
    signature = ElectronicSignature.objects.create(
        signer=user,
        signer_printed_name=user.get_full_name(),
        signer_role=user.role,
        meaning=meaning,
        entity_type=entity_type,
        entity_id=str(entity_id),
        record_hash=digest,
        reauthenticated=reauthenticated,
        ip_address=getattr(request, "_dx_client_ip", None),
        user_agent=(request.META.get("HTTP_USER_AGENT") if request else None),
        comment=comment,
    )

    event = record(
        action=AuditAction.RELEASE if meaning == ElectronicSignature.Meaning.RELEASE else AuditAction.UPDATE,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=f"signed: {signature.get_meaning_display()}",
        changes={"signature": {"old": None, "new": signature.manifest}, "record_hash": {"old": None, "new": digest}},
        reason=comment,
        blocking=True,
    )
    if event is not None:
        ElectronicSignature.objects.filter(pk=signature.pk).update(audit_sequence=event.sequence)
        signature.audit_sequence = event.sequence

    return signature



# ── 21 CFR Part 11 §11.300: account security ─────────────────────────────────


def security_state(user) -> AccountSecurityState:
    state, _ = AccountSecurityState.objects.get_or_create(user=user)
    return state


def register_failed_login(username: str) -> None:
    """Count a failed attempt and lock the account at the threshold."""
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(username=username).first()
    if user is None:
        return

    state = security_state(user)
    state.failed_attempts += 1
    state.last_failed_at = timezone.now()

    threshold = getattr(settings, "ACCOUNT_LOCKOUT_THRESHOLD", 5)
    if threshold and state.failed_attempts >= threshold:
        minutes = getattr(settings, "ACCOUNT_LOCKOUT_MINUTES", 30)
        state.locked_until = timezone.now() + timedelta(minutes=minutes)
        record(
            action=AuditAction.UPDATE,
            entity_type="accounts.User",
            entity_id=user.pk,
            entity_label=f"account locked: {user.username}",
            changes={"locked_until": {"old": None, "new": state.locked_until.isoformat()}},
            blocking=True,
        )
    state.save(update_fields=["failed_attempts", "last_failed_at", "locked_until"])


def register_successful_login(user) -> None:
    state = security_state(user)
    state.failed_attempts = 0
    state.locked_until = None
    state.last_activity_at = timezone.now()
    state.save(update_fields=["failed_attempts", "locked_until", "last_activity_at"])


def check_account_available(user) -> ControlCheck:
    state = security_state(user)
    if state.is_locked:
        return ControlCheck(
            False,
            f"This account is locked until {state.locked_until:%H:%M} after repeated failed sign-in attempts.",
            "21 CFR Part 11 §11.300(d)",
        )
    return ControlCheck(True)


def record_password_change(user, raw_password: str | None = None) -> None:
    """Store the new hash in history and reset the ageing clock."""
    state = security_state(user)
    state.password_changed_at = timezone.now()
    state.must_change_password = False
    state.save(update_fields=["password_changed_at", "must_change_password"])

    PasswordHistory.objects.create(user=user, password_hash=user.password)

    depth = getattr(settings, "PASSWORD_HISTORY_DEPTH", 5)
    stale = PasswordHistory.objects.filter(user=user).order_by("-created_at")[depth:]
    PasswordHistory.objects.filter(pk__in=[entry.pk for entry in stale]).delete()


def check_password_reuse(user, raw_password: str) -> ControlCheck:
    from django.contrib.auth.hashers import check_password

    depth = getattr(settings, "PASSWORD_HISTORY_DEPTH", 5)
    for entry in PasswordHistory.objects.filter(user=user).order_by("-created_at")[:depth]:
        if check_password(raw_password, entry.password_hash):
            return ControlCheck(
                False,
                f"This password was used recently. Choose one that differs from your last {depth}.",
                "21 CFR Part 11 §11.300(b)",
            )
    return ControlCheck(True)


# ── CAPA helpers ─────────────────────────────────────────────────────────────


def next_capa_reference() -> str:
    year = timezone.localdate().year
    count = CorrectiveAction.objects.filter(reference__startswith=f"CAPA-{year}-").count()
    return f"CAPA-{year}-{count + 1:04d}"


def raise_capa(
    *,
    title: str,
    category: str,
    description: str,
    raised_by,
    severity: str = CorrectiveAction.Severity.MEDIUM,
    linked_entity_type: str | None = None,
    linked_entity_id: str | None = None,
    patient_impact: bool = False,
) -> CorrectiveAction:
    """Open a nonconformance record. Called automatically by QC and PT failures."""
    return CorrectiveAction.objects.create(
        reference=next_capa_reference(),
        title=title[:255],
        category=category,
        severity=severity,
        description=description,
        raised_by=raised_by,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
        patient_impact=patient_impact,
        due_date=timezone.localdate() + timedelta(days=30),
    )
