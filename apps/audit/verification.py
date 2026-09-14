"""Chain integrity verification.

Walks the trail recomputing every hash. Any mismatch pinpoints the exact
sequence number at which the record was altered, which is what an inspector or
incident investigation needs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.utils import timezone

from apps.audit.hashing import GENESIS_HASH, hash_for_event
from apps.audit.models import AuditEvent, ChainCheckpoint, IntegrityAlert

logger = logging.getLogger("dx.audit")


@dataclass
class VerificationResult:
    ok: bool = True
    checked: int = 0
    head_sequence: int | None = None
    head_hash: str | None = None
    problems: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.ok = False
        self.problems.append(message)

    @property
    def summary(self) -> str:
        if self.ok:
            return f"Chain intact — {self.checked} event(s) verified through #{self.head_sequence or 0}."
        return f"Chain FAILED verification: {len(self.problems)} problem(s). " + "; ".join(self.problems[:5])


def verify_chain(start: int = 1, limit: int | None = None) -> VerificationResult:
    """Recompute the hash chain and report any discontinuity."""
    result = VerificationResult()

    queryset = AuditEvent.objects.filter(sequence__gte=start).order_by("sequence")
    if limit:
        queryset = queryset[:limit]

    expected_sequence = start
    previous_hash: str | None = None

    if start > 1:
        anchor = AuditEvent.objects.filter(sequence=start - 1).values("hash").first()
        if anchor is None:
            result.fail(f"No event at sequence {start - 1} to anchor a partial verification.")
            return result
        previous_hash = anchor["hash"]
    else:
        previous_hash = GENESIS_HASH

    for event in queryset.iterator(chunk_size=1000):
        if event.sequence != expected_sequence:
            result.fail(
                f"Sequence gap: expected #{expected_sequence}, found #{event.sequence}. "
                "Events appear to have been deleted."
            )
            expected_sequence = event.sequence

        if event.previous_hash != previous_hash:
            result.fail(
                f"Broken link at #{event.sequence}: stored previous_hash "
                f"{event.previous_hash[:12]}… does not match predecessor {(previous_hash or '')[:12]}…"
            )

        recomputed = hash_for_event(event)
        if recomputed != event.hash:
            result.fail(
                f"Tampered content at #{event.sequence} "
                f"({event.action} {event.entity_type}/{event.entity_id}): "
                f"recomputed {recomputed[:12]}… but stored {event.hash[:12]}…"
            )

        previous_hash = event.hash
        expected_sequence = event.sequence + 1
        result.checked += 1
        result.head_sequence = event.sequence
        result.head_hash = event.hash

    return result


def verify_and_checkpoint(*, raise_alert: bool = True) -> VerificationResult:
    """Verify the whole chain, record a checkpoint, and alert on failure."""
    result = verify_chain()

    ChainCheckpoint.objects.create(
        sequence=result.head_sequence or 0,
        head_hash=result.head_hash or GENESIS_HASH,
        event_count=result.checked,
        verified=result.ok,
        detail=result.summary,
    )

    if not result.ok and raise_alert:
        IntegrityAlert.objects.create(
            sequence=result.head_sequence,
            message=result.summary,
        )
        logger.error("AUDIT INTEGRITY FAILURE: %s", result.summary)

    return result


def latest_checkpoint() -> ChainCheckpoint | None:
    return ChainCheckpoint.objects.first()


def open_alerts():
    return IntegrityAlert.objects.filter(acknowledged_at__isnull=True)


def acknowledge_alert(alert_id: int, username: str) -> None:
    IntegrityAlert.objects.filter(pk=alert_id, acknowledged_at__isnull=True).update(
        acknowledged_by=username, acknowledged_at=timezone.now()
    )
