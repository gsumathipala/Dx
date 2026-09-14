"""Immutable, tamper-evident audit trail.

Design notes
------------
Every recorded event is linked to its predecessor by a SHA-256 hash chain:

    hash(n) = SHA256( canonical_payload(n) || hash(n-1) )

Altering or removing any historic row invalidates every hash after it, so
tampering is detectable even by someone with database write access. Appends are
serialised with a PostgreSQL advisory lock so the chain stays consistent across
multiple application workers, and ``AuditEvent`` refuses updates and deletes at
both the ORM level and — via triggers installed in migration 0002 — inside the
database itself.

This satisfies the "attributable, legible, contemporaneous, original and
accurate" (ALCOA+) expectations that CLIA/CAP inspections and 21 CFR Part 11
apply to laboratory records.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.common.constants import AuditAction


class AuditEventError(RuntimeError):
    """Raised when something attempts to mutate the immutable trail."""


class AuditSource(models.TextChoices):
    WEB = "web", "Web interface"
    API = "api", "API"
    INSTRUMENT = "instrument", "Instrument interface"
    SYSTEM = "system", "System / scheduled task"
    MIGRATION = "migration", "Data migration"
    CLI = "cli", "Management command"


class AuditEventQuerySet(models.QuerySet):
    def for_entity(self, entity_type: str, entity_id: str):
        return self.filter(entity_type=entity_type, entity_id=str(entity_id))

    def by_actor(self, username: str):
        return self.filter(actor_username=username)

    def between(self, start, end):
        qs = self
        if start:
            qs = qs.filter(timestamp__gte=start)
        if end:
            qs = qs.filter(timestamp__lte=end)
        return qs

    # The trail is append-only: block the bulk mutation paths too.
    def update(self, **kwargs):  # pragma: no cover - defensive
        raise AuditEventError("Audit events are immutable and cannot be updated.")

    def delete(self):  # pragma: no cover - defensive
        raise AuditEventError("Audit events are immutable and cannot be deleted.")


class AuditEvent(models.Model):
    """One recorded change. Append-only, hash-chained, never edited."""

    #: Monotonic position in the chain, assigned by the recorder under lock.
    #: It is also the primary key: a second auto-increment column would be a
    #: independent counter that can drift out of step with the chain (and does,
    #: after any restore that supplies explicit ids), giving two different
    #: answers to "which event is this".
    sequence = models.BigIntegerField(primary_key=True, editable=False)

    timestamp = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    recorded_at = models.DateTimeField(
        auto_now_add=True, help_text="When the event reached the trail (vs. when it happened)"
    )

    # ── Who ──────────────────────────────────────────────────────────────────
    actor_id = models.CharField(max_length=64, null=True, blank=True, editable=False)
    actor_username = models.CharField(max_length=150, default="system", editable=False, db_index=True)
    actor_role = models.CharField(max_length=32, null=True, blank=True, editable=False)

    # ── What ─────────────────────────────────────────────────────────────────
    entity_type = models.CharField(max_length=64, editable=False, db_index=True)
    entity_id = models.CharField(max_length=64, editable=False, db_index=True)
    entity_label = models.CharField(
        max_length=255, blank=True, default="", editable=False,
        help_text="Human-readable identity captured at event time",
    )
    action = models.CharField(max_length=48, choices=AuditAction.choices, editable=False, db_index=True)
    changes = models.JSONField(
        default=dict, editable=False,
        help_text="Field-level diff: {field: {'old': ..., 'new': ...}}",
    )
    reason = models.TextField(
        null=True, blank=True, editable=False,
        help_text="Justification supplied by the user, where the workflow requires one",
    )

    # ── Where from ───────────────────────────────────────────────────────────
    source = models.CharField(max_length=32, choices=AuditSource.choices, default=AuditSource.WEB, editable=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True, editable=False)
    user_agent = models.TextField(null=True, blank=True, editable=False)
    request_id = models.CharField(max_length=64, null=True, blank=True, editable=False, db_index=True)
    session_key = models.CharField(max_length=64, null=True, blank=True, editable=False)

    # ── Tamper evidence ──────────────────────────────────────────────────────
    previous_hash = models.CharField(max_length=64, editable=False)
    hash = models.CharField(max_length=64, unique=True, editable=False)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        db_table = "audit_events"
        ordering = ["-sequence"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "-sequence"], name="audit_entity_idx"),
            models.Index(fields=["actor_username", "-timestamp"], name="audit_actor_idx"),
            models.Index(fields=["action", "-timestamp"], name="audit_action_idx"),
            models.Index(fields=["-timestamp"], name="audit_time_idx"),
        ]
        verbose_name = "audit event"
        verbose_name_plural = "audit trail"

    def __str__(self) -> str:
        return f"#{self.sequence} {self.action} {self.entity_type}/{self.entity_id} by {self.actor_username}"

    # ── Immutability guards ──────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise AuditEventError("Audit events are immutable and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditEventError("Audit events are immutable and cannot be deleted.")

    # ── Presentation helpers ─────────────────────────────────────────────────

    @property
    def changed_fields(self) -> list[str]:
        return sorted((self.changes or {}).keys())

    @property
    def is_genesis(self) -> bool:
        return self.sequence == 1

    def change_rows(self) -> list[dict]:
        """Flatten ``changes`` into template-friendly rows."""
        rows = []
        for field, delta in sorted((self.changes or {}).items()):
            if isinstance(delta, dict):
                rows.append({"field": field, "old": delta.get("old"), "new": delta.get("new")})
            else:
                rows.append({"field": field, "old": None, "new": delta})
        return rows


class ChainCheckpoint(models.Model):
    """Periodic notarisation of the chain head.

    The integrity monitor writes a checkpoint after each successful verification
    so a later audit can prove the trail was intact at a known point in time
    without re-reading the whole history.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sequence = models.BigIntegerField(help_text="Chain head at checkpoint time")
    head_hash = models.CharField(max_length=64)
    event_count = models.BigIntegerField()
    verified = models.BooleanField(default=True)
    detail = models.TextField(blank=True, default="")

    class Meta:
        db_table = "audit_chain_checkpoints"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        state = "ok" if self.verified else "BROKEN"
        return f"checkpoint @ {self.sequence} ({state})"


class IntegrityAlert(models.Model):
    """Raised when chain verification fails — never auto-resolved silently."""

    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sequence = models.BigIntegerField(null=True, blank=True)
    message = models.TextField()
    acknowledged_by = models.CharField(max_length=150, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "audit_integrity_alerts"
        ordering = ["-detected_at"]

    def __str__(self) -> str:
        return f"integrity alert @ {self.sequence}: {self.message[:60]}"
