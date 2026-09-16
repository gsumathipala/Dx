"""Pessimistic record locking.

Two scientists entering results on the same order is not a merge conflict — it
is one of them silently overwriting the other, on a record that a clinician
will act on. Optimistic concurrency (detect the collision at save time and ask
somebody to redo their work) is the right answer for a wiki and the wrong
answer here: by the time the second person is told, they have already typed
forty analytes.

So the lock is **pessimistic and visible**. Opening a patient record or a
result-entry screen takes the lock; anybody else arriving sees who holds it and
gets a read-only view, not a form that will fail on submit.

Why locks expire
----------------
A browser tab closed without warning, a laptop that slept, a session that
ended in a power cut — any of these would otherwise leave a record locked
forever, and the laboratory would learn to route around the locking rather
than trust it. Locks therefore carry a TTL (``RECORD_LOCK_TTL_SECONDS``,
default 15 minutes) which the open page refreshes with a heartbeat. A lock
whose holder has gone quiet for longer than the TTL is taken over
automatically by the next person who needs it.

The three ways a lock is released
---------------------------------
1. **The holder leaves.** An explicit release on navigating away, sent with
   ``navigator.sendBeacon`` so it survives the page unloading, plus an
   explicit release when a save completes and when the user signs out.
2. **It expires.** The backstop above.
3. **An administrator breaks it.** For the case the first two do not cover —
   somebody is off shift with the record still open. Breaking a lock is
   recorded in the audit trail with a reason, because it is an override of a
   control, and because "who unlocked this and why" is the first question
   after two people's edits collide.

Locks are advisory over *editing screens*, not a database-level guarantee.
They cannot stop a direct ORM write, and are not meant to: the transactional
integrity of a save is the database's job. This stops two people being
*handed a form* for the same record.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import RecordLock

logger = logging.getLogger("dx.locking")

#: Roles permitted to break another user's lock.
from apps.common.constants import Role  # noqa: E402  (kept next to its use)

BREAKER_ROLES = (Role.ADMIN, Role.MANAGER, Role.INSTALLER)


def ttl_seconds() -> int:
    return int(getattr(settings, "RECORD_LOCK_TTL_SECONDS", 900))


@dataclass(frozen=True)
class LockState:
    """What a view needs to know about a record's lock.

    ``editable`` is the single thing a template should branch on. It is
    deliberately not "is there a lock" — the holder of a lock may edit, and so
    may somebody arriving at an unlocked record.
    """

    lock: RecordLock | None
    held_by_me: bool
    editable: bool
    #: True when the caller could not take the lock because somebody else has it.
    blocked: bool = False

    @property
    def holder(self) -> str:
        return self.lock.username if self.lock else ""

    @property
    def held_since(self):
        return self.lock.timestamp if self.lock else None

    @property
    def expires_at(self):
        return self.lock.expires_at if self.lock else None

    @property
    def message(self) -> str:
        if not self.blocked or self.lock is None:
            return ""
        return (
            f"This record is open by {self.lock.username} since "
            f"{self.lock.timestamp:%H:%M}. You can read it, but not change it, "
            f"until they close it or the lock expires at "
            f"{self.lock.expires_at:%H:%M}."
        )


def _purge_expired(entity_type: str, entity_id: str) -> None:
    RecordLock.objects.filter(
        entity_type=entity_type, entity_id=str(entity_id),
        expires_at__lte=timezone.now(),
    ).delete()


def current(entity_type: str, entity_id) -> RecordLock | None:
    """The live lock on a record, or None. Expired locks are not live."""
    return RecordLock.objects.filter(
        entity_type=entity_type, entity_id=str(entity_id),
        expires_at__gt=timezone.now(),
    ).select_related("user").first()


def acquire(entity_type: str, entity_id, user, *, ttl: int | None = None) -> LockState:
    """Take or refresh the lock on a record.

    Returns a :class:`LockState`. The caller is editable when it holds the
    lock; when somebody else does, the caller is blocked and should render
    read-only rather than raising — a colleague being in the record first is
    normal, not an error.
    """
    entity_id = str(entity_id)
    expires = timezone.now() + timedelta(seconds=ttl or ttl_seconds())

    with transaction.atomic():
        _purge_expired(entity_type, entity_id)

        existing = (
            RecordLock.objects
            .select_for_update()
            .filter(entity_type=entity_type, entity_id=entity_id)
            .select_related("user")
            .first()
        )

        if existing is not None:
            if existing.user_id == user.pk:
                existing.expires_at = expires
                existing.save(update_fields=["expires_at"])
                return LockState(lock=existing, held_by_me=True, editable=True)
            return LockState(
                lock=existing, held_by_me=False, editable=False, blocked=True
            )

        try:
            lock = RecordLock.objects.create(
                entity_type=entity_type, entity_id=entity_id,
                user=user, username=user.username, expires_at=expires,
            )
        except IntegrityError:
            # Someone took it between the purge and the insert. Re-read rather
            # than retrying blindly: the winner is whoever the database says.
            other = current(entity_type, entity_id)
            if other is None or other.user_id == user.pk:
                return acquire(entity_type, entity_id, user, ttl=ttl)
            return LockState(lock=other, held_by_me=False, editable=False, blocked=True)

        return LockState(lock=lock, held_by_me=True, editable=True)


def heartbeat(entity_type: str, entity_id, user) -> bool:
    """Extend the caller's own lock. False if they no longer hold it."""
    updated = RecordLock.objects.filter(
        entity_type=entity_type, entity_id=str(entity_id), user=user,
    ).update(expires_at=timezone.now() + timedelta(seconds=ttl_seconds()))
    return bool(updated)


def release(entity_type: str, entity_id, user) -> bool:
    """Give up a lock the caller holds. Releasing one you do not hold is a no-op.

    Deliberately silent rather than an error: a stale browser tab firing its
    release beacon after the lock has already expired and been taken by
    somebody else must not remove *their* lock.
    """
    deleted, _ = RecordLock.objects.filter(
        entity_type=entity_type, entity_id=str(entity_id), user=user,
    ).delete()
    return bool(deleted)


def release_all_for(user) -> int:
    """Drop every lock a user holds — used at sign-out."""
    deleted, _ = RecordLock.objects.filter(user=user).delete()
    return deleted


def may_break(user) -> bool:
    return bool(user and user.is_authenticated and user.role in BREAKER_ROLES)


def break_lock(lock: RecordLock, *, by_user, reason: str) -> None:
    """Force a lock open. Audited, because it overrides a control.

    The reason is mandatory. After two people's edits collide, the first
    question is who unlocked the record and why, and an unexplained override
    makes that unanswerable.
    """
    from apps.audit.recorder import record
    from apps.common.constants import AuditAction
    from apps.compliance.services import ControlViolation

    if not may_break(by_user):
        raise ControlViolation(
            "Only a manager, administrator or the installer may break a record lock."
        )
    if not (reason or "").strip():
        raise ControlViolation(
            "Give a reason for breaking the lock — it is recorded against the record."
        )

    holder, entity_type, entity_id = lock.username, lock.entity_type, lock.entity_id
    lock.delete()

    record(
        action=AuditAction.UPDATE,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=f"record lock held by {holder} broken by {by_user.username}",
        changes={"lock": {"old": holder, "new": None}},
        reason=reason.strip(),
        blocking=True,
    )
    logger.info(
        "Lock on %s/%s held by %s broken by %s: %s",
        entity_type, entity_id, holder, by_user.username, reason.strip(),
    )


def purge_all_expired() -> int:
    """Housekeeping — expired locks are ignored anyway, but do not accumulate."""
    deleted, _ = RecordLock.objects.filter(expires_at__lte=timezone.now()).delete()
    return deleted
