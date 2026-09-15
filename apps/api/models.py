"""API clients and outbound webhooks.

The application already speaks HL7 and FHIR, which is what a hospital
integration engine wants. What a hospital's *own* developers want — the ward
dashboard, the audit extract, the research pull — is an ordinary JSON API with
tokens they can rotate themselves, and a way to be told when something happens
instead of polling for it.

Both are patient data leaving the building, so both are treated as disclosures:
every client is named, scoped, logged and revocable, and everything it reads is
recorded against HIPAA disclosure accounting the same way a screen view is.
"""
from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from apps.common.models import ActivatableModel, IdentifiedModel


class Scope(models.TextChoices):
    """What a client is allowed to do.

    Scopes are deliberately coarse — one per resource and verb. Fine-grained
    scopes look rigorous and end up being granted wholesale because nobody can
    reason about forty of them.
    """

    CATALOGUE_READ = "catalogue:read", "Read the test catalogue and terminologies"
    PATIENTS_READ = "patients:read", "Read patient demographics"
    PATIENTS_WRITE = "patients:write", "Register and update patients"
    ORDERS_READ = "orders:read", "Read orders"
    ORDERS_WRITE = "orders:write", "Place orders"
    RESULTS_READ = "results:read", "Read results"
    REPORTS_READ = "reports:read", "Read reports, including FHIR and HL7 renderings"
    EXCEPTIONS_READ = "exceptions:read", "Read the exception queue"
    WEBHOOKS_MANAGE = "webhooks:manage", "Create and remove webhook subscriptions"


#: Scopes that expose identifiable patient information. Granting one of these
#: makes the client a recipient of PHI, which has consequences for disclosure
#: accounting and for what the installer role may see.
PHI_SCOPES = frozenset({
    Scope.PATIENTS_READ, Scope.PATIENTS_WRITE, Scope.ORDERS_READ,
    Scope.ORDERS_WRITE, Scope.RESULTS_READ, Scope.REPORTS_READ,
    Scope.EXCEPTIONS_READ,
})


class ApiClient(IdentifiedModel, ActivatableModel):
    """A named machine consumer of the API.

    The secret is stored as a password hash and shown exactly once, at
    creation. A system that can show you a credential again is a system that
    stores it in a form an attacker can use.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    key_id = models.CharField(max_length=32, unique=True, editable=False)
    secret_hash = models.CharField(max_length=255, editable=False)
    scopes = models.JSONField(default=list, blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="api_clients", help_text="Who is accountable for this client.",
    )
    organisation = models.CharField(
        max_length=255, blank=True,
        help_text="The receiving organisation, named on disclosure records.",
    )
    purpose = models.CharField(
        max_length=255, blank=True,
        help_text="Why this client exists — required for the minimum necessary standard.",
    )

    allowed_ips = models.JSONField(
        default=list, blank=True,
        help_text="Optional allow-list of source addresses. Empty means any.",
    )
    rate_limit_per_minute = models.PositiveIntegerField(default=120)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text="After this, the credential stops working."
    )
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)
    request_count = models.BigIntegerField(default=0, editable=False)

    class Meta:
        db_table = "api_clients"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    # ── Credentials ──────────────────────────────────────────────────────────

    @classmethod
    def issue(cls, **fields) -> tuple["ApiClient", str]:
        """Create a client and return it with its one-time secret."""
        key_id = secrets.token_hex(8)
        secret = secrets.token_urlsafe(32)
        client = cls.objects.create(
            key_id=key_id, secret_hash=make_password(secret), **fields
        )
        return client, f"{key_id}.{secret}"

    def rotate_secret(self) -> str:
        secret = secrets.token_urlsafe(32)
        self.secret_hash = make_password(secret)
        self.save(update_fields=["secret_hash"])
        return f"{self.key_id}.{secret}"

    def verify(self, secret: str) -> bool:
        return check_password(secret, self.secret_hash)

    # ── State ────────────────────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_usable(self) -> bool:
        return self.active and not self.is_expired

    @property
    def handles_phi(self) -> bool:
        return bool(PHI_SCOPES.intersection(self.scopes or []))

    @property
    def scope_display(self) -> str:
        return ", ".join(self.scopes or []) or "none"

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])


class Webhook(IdentifiedModel, ActivatableModel):
    """A subscription to events, delivered by signed HTTP POST.

    Each delivery carries an HMAC-SHA256 signature over a timestamp and the
    body, so the receiver can prove the payload came from this installation and
    has not been replayed. That is the whole security model — we do not assume
    the receiver's TLS certificate validation is correctly configured, because
    frequently it is not.
    """

    class Event(models.TextChoices):
        ORDER_CREATED = "order.created", "Order accessioned"
        ORDER_COMPLETED = "order.completed", "Order completed"
        RESULT_ENTERED = "result.entered", "Result entered"
        RESULT_VERIFIED = "result.verified", "Result clinically verified"
        REPORT_RELEASED = "report.released", "Report released"
        CRITICAL_VALUE = "critical_value.raised", "Critical value raised"
        AMENDED_REPORT = "report.amended", "Report amended after release"
        EXCEPTION_RAISED = "exception.raised", "Exception queue item raised"
        QC_FAILED = "qc.failed", "Quality control failed"

    name = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    secret = models.CharField(max_length=128, editable=False, default=secrets.token_urlsafe)
    events = models.JSONField(default=list, blank=True)
    client = models.ForeignKey(
        ApiClient, null=True, blank=True, on_delete=models.CASCADE, related_name="webhooks"
    )

    include_identifiers = models.BooleanField(
        default=False,
        help_text=(
            "Send patient identifiers in the payload. Off by default: most "
            "subscribers only need to know something happened and can fetch "
            "the detail over the API, which is logged."
        ),
    )
    consecutive_failures = models.PositiveIntegerField(default=0, editable=False)
    disabled_reason = models.CharField(max_length=255, blank=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "webhooks"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} → {self.url}"

    def subscribes_to(self, event: str) -> bool:
        return self.active and event in (self.events or [])

    def rotate_secret(self) -> str:
        self.secret = secrets.token_urlsafe(32)
        self.save(update_fields=["secret"])
        return self.secret


class WebhookDelivery(IdentifiedModel):
    """One attempt series to deliver one event to one subscriber.

    Retries use exponential backoff and stop after
    ``MAX_ATTEMPTS``. A permanently failing subscriber raises an item on the
    exception queue rather than silently dropping events — an integration that
    quietly stopped working is how a ward finds out about a critical result by
    telephone three days later.
    """

    MAX_ATTEMPTS = 6
    #: Backoff in seconds per attempt: ~30s, 2m, 8m, 30m, 2h.
    BACKOFF = (30, 120, 480, 1800, 7200)

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        RETRYING = "retrying", "Retrying"
        FAILED = "failed", "Failed"

    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name="deliveries")
    event = models.CharField(max_length=48)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    response_code = models.PositiveIntegerField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "webhook_deliveries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"]),
            models.Index(fields=["webhook", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event} → {self.webhook_id} ({self.status})"

    def schedule_retry(self, error: str, response_code: int | None = None) -> None:
        self.attempts += 1
        self.last_error = (error or "")[:2000]
        self.response_code = response_code
        if self.attempts >= self.MAX_ATTEMPTS:
            self.status = self.Status.FAILED
        else:
            self.status = self.Status.RETRYING
            delay = self.BACKOFF[min(self.attempts - 1, len(self.BACKOFF) - 1)]
            self.next_attempt_at = timezone.now() + timedelta(seconds=delay)
        self.save(update_fields=[
            "attempts", "last_error", "response_code", "status", "next_attempt_at",
        ])

    def mark_delivered(self, response_code: int) -> None:
        self.attempts += 1
        self.status = self.Status.DELIVERED
        self.response_code = response_code
        self.delivered_at = timezone.now()
        self.last_error = ""
        self.save(update_fields=[
            "attempts", "status", "response_code", "delivered_at", "last_error",
        ])
