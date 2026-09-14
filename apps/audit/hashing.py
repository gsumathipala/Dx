"""Canonical serialisation and hash-chain arithmetic for the audit trail.

The payload must serialise identically on every machine and every Python
version, otherwise verification would produce false tamper alarms. We therefore
use JSON with sorted keys, no insignificant whitespace, and explicit coercion of
non-JSON-native values to strings.
"""
from __future__ import annotations

import datetime
import decimal
import hashlib
import json
import uuid
from typing import Any

#: Hash recorded as the predecessor of the very first event.
GENESIS_HASH = "0" * 64


def _coerce(value: Any) -> Any:
    """Convert a value into something JSON can represent deterministically."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, decimal.Decimal):
        return format(value, "f")
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _coerce(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        items = [_coerce(v) for v in value]
        return sorted(items, key=repr) if isinstance(value, set) else items
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def canonical_json(payload: dict) -> str:
    """Stable JSON encoding used as hash input."""
    return json.dumps(
        _coerce(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def event_payload(
    *,
    sequence: int,
    timestamp,
    actor_id,
    actor_username,
    actor_role,
    entity_type,
    entity_id,
    entity_label,
    action,
    changes,
    reason,
    source,
    ip_address,
    user_agent,
    request_id,
    session_key,
) -> dict:
    """The exact field set covered by the signature.

    Anything omitted here is not protected by the chain, so every field that
    carries evidential weight must appear.
    """
    return {
        "sequence": sequence,
        "timestamp": timestamp,
        "actor_id": actor_id,
        "actor_username": actor_username,
        "actor_role": actor_role,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_label": entity_label,
        "action": action,
        "changes": changes,
        "reason": reason,
        "source": source,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "request_id": request_id,
        "session_key": session_key,
    }


def compute_hash(payload: dict, previous_hash: str) -> str:
    """Link ``payload`` to its predecessor and return the chain hash."""
    material = f"{canonical_json(payload)}|{previous_hash}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def hash_for_event(event) -> str:
    """Recompute the stored hash of a persisted ``AuditEvent``."""
    payload = event_payload(
        sequence=event.sequence,
        timestamp=event.timestamp,
        actor_id=event.actor_id,
        actor_username=event.actor_username,
        actor_role=event.actor_role,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        entity_label=event.entity_label,
        action=event.action,
        changes=event.changes,
        reason=event.reason,
        source=event.source,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        request_id=event.request_id,
        session_key=event.session_key,
    )
    return compute_hash(payload, event.previous_hash)
