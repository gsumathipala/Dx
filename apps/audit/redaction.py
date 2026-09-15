"""Hides patient identifiers from roles barred from seeing them.

The installer needs the audit trail to do its job: to confirm the chain is
intact, that the recorder is running, and that changes are attributable. It
does not need to know *which patient* a change concerned.

So clinical events are shown redacted rather than withheld. An installer still
sees the sequence number, the time, who acted, what kind of record it was, the
action, and the hashes — everything system assurance rests on — with the
content removed.

What counts as an identifier
----------------------------
Names, medical record numbers, dates of birth, contact details and addresses
are obvious. Two less obvious ones are redacted as well:

* **Accession numbers.** A specimen identifier tied to one patient's episode.
* **Primary keys.** HIPAA's Safe Harbor list includes "any other unique
  identifying number, characteristic, or code" (45 CFR §164.514(b)(2)(i)(R)).
  A record's UUID is exactly that, so it is replaced by a short keyed digest —
  which still lets an installer see that several events concern the same
  record, without handing them a key they could use to address it.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from django.conf import settings

#: Applications whose records describe patients or their specimens.
PHI_BEARING_APPS = frozenset({
    "patients", "laboratory", "clinical", "specialty", "reporting", "billing",
})

#: Individual models elsewhere that carry patient identifiers.
PHI_BEARING_MODELS = frozenset({
    "compliance.PHIAccessLog",
    "compliance.DisclosureAccounting",
    "compliance.PatientConsent",
    "compliance.AmendedReport",
    "operations.ChainOfCustodyEvent",
    "operations.StorageAssignment",
    "operations.Aliquot",
    "interop.InstrumentMessage",
})

REDACTED = "[redacted]"


def is_phi_bearing(entity_type: str) -> bool:
    """Whether a record of this type can carry a patient identifier."""
    if not entity_type:
        return False
    if entity_type in PHI_BEARING_MODELS:
        return True
    return entity_type.split(".", 1)[0] in PHI_BEARING_APPS


def may_see_clinical_content(user) -> bool:
    return bool(user and user.is_authenticated and user.may_see_patient_data)


def record_token(entity_id: str) -> str:
    """A short, stable, non-reversible stand-in for a record's key.

    Keyed with the installation's secret so it cannot be reversed by hashing
    candidate identifiers, and stable so several events about the same record
    are still recognisably about the same record.
    """
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        str(entity_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"ref:{digest[:10]}"


@dataclass(frozen=True)
class RedactedEvent:
    """An audit event with its clinical content removed.

    Presents the same attributes the templates read from ``AuditEvent``, so the
    trail renders identically whether or not redaction applied.
    """

    sequence: int
    timestamp: object
    recorded_at: object
    actor_username: str
    actor_role: str | None
    action: str
    entity_type: str
    entity_id: str
    entity_label: str
    changes: dict
    reason: str | None
    source: str
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    session_key: str | None
    previous_hash: str
    hash: str
    redacted: bool = True

    # ── The interface the templates use ──────────────────────────────────────

    @property
    def changed_fields(self) -> list[str]:
        return sorted((self.changes or {}).keys())

    @property
    def is_genesis(self) -> bool:
        return self.sequence == 1

    def change_rows(self) -> list[dict]:
        return [
            {"field": field, "old": delta.get("old"), "new": delta.get("new")}
            for field, delta in sorted((self.changes or {}).items())
        ]

    def get_action_display(self) -> str:
        return self.action

    def get_source_display(self) -> str:
        return self.source


def redact_event(event) -> RedactedEvent:
    """Strip the clinical content from one event.

    Which fields changed is kept — that a patient's surname was edited is
    itself useful for system assurance — while the values are removed.
    """
    return RedactedEvent(
        sequence=event.sequence,
        timestamp=event.timestamp,
        recorded_at=event.recorded_at,
        actor_username=event.actor_username,
        actor_role=event.actor_role,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=record_token(event.entity_id),
        entity_label=f"{event.entity_type.split('.')[-1]} {REDACTED}",
        changes={
            field: {"old": REDACTED, "new": REDACTED}
            for field in (event.changes or {})
        },
        # A free-text reason is written by a person and may name a patient.
        reason=REDACTED if event.reason else None,
        source=event.source,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        request_id=event.request_id,
        session_key=event.session_key,
        previous_hash=event.previous_hash,
        hash=event.hash,
    )


def apply(events, user):
    """Redact whichever of ``events`` this user may not see in full."""
    if may_see_clinical_content(user):
        return list(events)
    return [
        redact_event(event) if is_phi_bearing(event.entity_type) else event
        for event in events
    ]
