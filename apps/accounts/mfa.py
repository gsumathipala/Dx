"""Time-based one-time passwords (RFC 6238).

Implemented against the RFC rather than pulled in as a dependency. TOTP is
about sixty lines — an HMAC, a truncation and a clock — and every authenticator
app in existence implements the same thing. Adding a library for it would add a
supply-chain surface to a security control for no benefit.

What this defends against
-------------------------
A stolen or phished password. That is the whole claim, and it is worth being
precise about it: TOTP does **not** defend against a compromised workstation,
a session token stolen after login, or a user who approves a prompt they did
not initiate. It raises the cost of remote credential reuse, which is the
attack laboratories actually see.

Storage
-------
The shared secret is equivalent to a password and is encrypted at rest with
AES-256-GCM under a key derived from ``SECRET_KEY``. That protects it in a
database dump; it does not protect it from somebody who has the application's
configuration, and nothing short of an HSM would.

Replay
------
A code is valid for a 30-second step, and the previous and next steps are
accepted to allow for clock drift. ``last_step`` records the step a code was
accepted at and refuses anything at or below it, so a code observed over
somebody's shoulder cannot be used twice inside its own window.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import struct
import time
from urllib.parse import quote

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import IdentifiedModel

logger = logging.getLogger("dx.mfa")

DIGITS = 6
STEP_SECONDS = 30
#: Steps either side of now that are accepted, for clock drift.
DRIFT_STEPS = 1
SECRET_BYTES = 20  # 160 bits, as RFC 4226 §4 requires
RECOVERY_CODE_COUNT = 10


# ── The algorithm ────────────────────────────────────────────────────────────


def generate_secret() -> str:
    """A fresh base32 shared secret, in the form authenticator apps expect."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii").rstrip("=")


def _step_at(when: float | None = None) -> int:
    return int((when if when is not None else time.time()) // STEP_SECONDS)


def code_for(secret: str, step: int) -> str:
    """The TOTP code for one time step. RFC 6238 §4, RFC 4226 §5.3."""
    padding = "=" * (-len(secret) % 8)
    key = base64.b32decode(secret + padding, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()

    # Dynamic truncation: the low nibble of the last byte picks the offset.
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10**DIGITS)).zfill(DIGITS)


def verify_code(secret: str, presented: str, *, after_step: int = 0,
                when: float | None = None) -> int | None:
    """Check a code. Returns the step it matched, or None.

    ``after_step`` refuses anything at or below a step already used, so a code
    cannot be replayed inside its own validity window.
    """
    presented = (presented or "").strip().replace(" ", "")
    if not presented.isdigit() or len(presented) != DIGITS:
        return None

    now = _step_at(when)
    for offset in range(-DRIFT_STEPS, DRIFT_STEPS + 1):
        step = now + offset
        if step <= after_step:
            continue
        if hmac.compare_digest(code_for(secret, step), presented):
            return step
    return None


def provisioning_uri(secret: str, *, username: str, issuer: str = "Dx LIS") -> str:
    """The ``otpauth://`` URI an authenticator app scans."""
    label = quote(f"{issuer}:{username}")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"
    )


# ── Secret storage ───────────────────────────────────────────────────────────


def _key() -> str:
    """Key material for encrypting stored secrets, derived from SECRET_KEY.

    Derived rather than used directly so that rotating SECRET_KEY for session
    signing does not silently succeed here and then fail to decrypt.
    """
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), b"dx-mfa-secret-v1", hashlib.sha256
    ).hexdigest()


def seal(secret: str) -> bytes:
    from apps.compliance.encryption import encrypt_bytes

    return encrypt_bytes(secret.encode("ascii"), _key())


def unseal(sealed: bytes) -> str:
    from apps.compliance.encryption import decrypt_bytes

    return decrypt_bytes(bytes(sealed), _key()).decode("ascii")


# ── Models ───────────────────────────────────────────────────────────────────


class MfaDevice(IdentifiedModel):
    """One authenticator binding per user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_device"
    )
    sealed_secret = models.BinaryField(editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    #: Null until the user has proved they can produce a code. An unconfirmed
    #: device must never gate a login: locking somebody out with a secret they
    #: failed to scan is the classic way to make a laboratory disable MFA.
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_step = models.BigIntegerField(default=0, editable=False)
    failed_attempts = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "mfa_devices"

    def __str__(self) -> str:
        return f"authenticator for {self.user_id}"

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None

    @property
    def secret(self) -> str:
        return unseal(self.sealed_secret)

    def verify(self, presented: str) -> bool:
        """Check a code and, on success, burn the step it used."""
        step = verify_code(self.secret, presented, after_step=self.last_step)
        if step is None:
            self.failed_attempts += 1
            self.save(update_fields=["failed_attempts"])
            return False

        self.last_step = step
        self.last_used_at = timezone.now()
        self.failed_attempts = 0
        self.save(update_fields=["last_step", "last_used_at", "failed_attempts"])
        return True


class MfaRecoveryCode(IdentifiedModel):
    """A single-use way back in when the authenticator is gone.

    Stored as a hash. A recovery code is a credential; a system that can show
    you one again stores it in a form an attacker can use.

    Without these, a lost phone means an administrator resetting somebody's
    second factor — which is a social-engineering route straight through the
    control MFA exists to provide.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_recovery_codes"
    )
    code_hash = models.CharField(max_length=128, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mfa_recovery_codes"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"recovery code for {self.user_id} ({'used' if self.used_at else 'unused'})"


def _hash_recovery(code: str) -> str:
    return hmac.new(
        _key().encode("utf-8"), code.strip().lower().encode("utf-8"), hashlib.sha256
    ).hexdigest()


def issue_recovery_codes(user, *, count: int = RECOVERY_CODE_COUNT) -> list[str]:
    """Replace a user's recovery codes and return the new ones, once."""
    MfaRecoveryCode.objects.filter(user=user).delete()
    codes = []
    for _ in range(count):
        raw = f"{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}"
        codes.append(raw)
        MfaRecoveryCode.objects.create(user=user, code_hash=_hash_recovery(raw))
    return codes


def consume_recovery_code(user, presented: str) -> bool:
    """Spend a recovery code. Each works exactly once."""
    candidate = MfaRecoveryCode.objects.filter(
        user=user, code_hash=_hash_recovery(presented), used_at__isnull=True
    ).first()
    if candidate is None:
        return False
    candidate.used_at = timezone.now()
    candidate.save(update_fields=["used_at"])
    return True


def unused_recovery_code_count(user) -> int:
    return MfaRecoveryCode.objects.filter(user=user, used_at__isnull=True).count()


# ── Policy ───────────────────────────────────────────────────────────────────


def required_roles() -> tuple[str, ...]:
    """Roles for which a second factor is mandatory.

    Defaults to the two roles that can change who else has access. Somebody
    who can create an administrator account is a far more valuable target than
    somebody who can enter a potassium.
    """
    from apps.common.constants import Role

    configured = getattr(settings, "MFA_REQUIRED_ROLES", None)
    if configured is None:
        return (Role.ADMIN, Role.INSTALLER)
    return tuple(configured)


def is_required_for(user) -> bool:
    if not getattr(settings, "MFA_ENABLED", True):
        return False
    return user.role in required_roles()


def device_for(user) -> MfaDevice | None:
    device = MfaDevice.objects.filter(user=user).first()
    return device if device is not None and device.is_confirmed else None


def state_for(user) -> dict:
    """What the account screen needs to say about this user's second factor."""
    device = MfaDevice.objects.filter(user=user).first()
    return {
        "enrolled": bool(device and device.is_confirmed),
        "pending": bool(device and not device.is_confirmed),
        "required": is_required_for(user),
        "recovery_codes_left": unused_recovery_code_count(user),
        "last_used_at": device.last_used_at if device else None,
    }
