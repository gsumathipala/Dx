"""The persistent audit recorder.

Events are handed to an in-process queue and drained by a long-lived daemon
thread, so request latency never depends on the audit write. The thread appends
under a PostgreSQL advisory lock, which keeps the hash chain consistent even
when several gunicorn workers (or the instrument server, or a cron job) record
concurrently.

Durability
----------
Losing an audit event is not acceptable in a clinical system, so:

* ``record()`` can be called synchronously (``blocking=True``) and is, for the
  events that must not be lost — signatures, verifications, releases, logins.
* The queue is bounded; if it ever fills, the producer falls back to a
  synchronous write rather than dropping the event.
* On shutdown the thread drains what is left before exiting.
* Any event that still cannot be written is serialised to the spool file so it
  can be replayed with ``manage.py audit_replay_spool``.
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import queue
import threading
import time
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.audit.context import AuditContext, get_context
from apps.audit.hashing import GENESIS_HASH, compute_hash, event_payload
from apps.audit.models import AuditEvent, AuditSource

logger = logging.getLogger("dx.audit")

#: Namespaced PostgreSQL advisory lock id guarding chain appends.
CHAIN_LOCK_ID = 8_417_233_901

_QUEUE_MAXSIZE = int(os.environ.get("AUDIT_QUEUE_MAXSIZE", "10000"))
_SHUTDOWN = object()


def spool_path() -> Path:
    configured = getattr(settings, "AUDIT_SPOOL_FILE", None)
    if configured:
        return Path(configured)
    return Path(settings.BASE_DIR) / "audit-spool.jsonl"


class AuditRecorder:
    """Owns the queue, the writer thread and the chain head."""

    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._drained = threading.Event()
        self._drained.set()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the persistent writer thread (idempotent)."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._running.set()
            self._thread = threading.Thread(
                target=self._run, name="dx-audit-recorder", daemon=True
            )
            self._thread.start()
            atexit.register(self.shutdown)
            logger.info("Audit recorder thread started")

    def shutdown(self, timeout: float = 10.0) -> None:
        """Stop accepting work and flush the backlog."""
        if not self._running.is_set():
            return
        self._running.clear()
        try:
            self._queue.put_nowait(_SHUTDOWN)
        except queue.Full:  # pragma: no cover - drain will exit on the flag
            pass
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        logger.info("Audit recorder thread stopped")

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def pending(self) -> int:
        return self._queue.qsize()

    def flush(self, timeout: float = 5.0) -> bool:
        """Block until the queue is empty. Returns False on timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._queue.empty() and self._drained.is_set():
                return True
            time.sleep(0.01)
        return self._queue.empty()

    # ── Producer side ────────────────────────────────────────────────────────

    def record(self, event: dict, *, blocking: bool = False) -> AuditEvent | None:
        """Queue an event, or write it straight through when ``blocking``.

        A blocking write first drains the queue. Without that, a synchronous
        event would overtake earlier queued ones and the chain would record a
        delete before the create that preceded it — the sequence must reflect
        the order things actually happened.
        """
        if blocking or not self.is_running():
            if self.is_running() and not self._queue.empty():
                self.flush(timeout=5.0)
            return self._append_with_retry(event)
        try:
            self._drained.clear()
            self._queue.put_nowait(event)
        except queue.Full:
            logger.warning("Audit queue saturated — writing event synchronously")
            return self._append_with_retry(event)
        return None

    # ── Consumer side ────────────────────────────────────────────────────────

    def _run(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                self._drained.set()
                if not self._running.is_set():
                    return
                continue

            if item is _SHUTDOWN:
                self._drain_remaining()
                return

            try:
                self._append_with_retry(item)
            except Exception:  # pragma: no cover - last line of defence
                logger.exception("Audit recorder failed to persist an event")
            finally:
                self._queue.task_done()
                if self._queue.empty():
                    self._drained.set()

    def _drain_remaining(self) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                self._drained.set()
                return
            if item is _SHUTDOWN:
                continue
            try:
                self._append_with_retry(item)
            except Exception:  # pragma: no cover
                logger.exception("Audit recorder failed during drain")
            finally:
                self._queue.task_done()

    # ── Chain append ─────────────────────────────────────────────────────────

    def _append_with_retry(self, event: dict, attempts: int = 3) -> AuditEvent | None:
        """Append, retrying transient database failures.

        Retrying is only meaningful when we own the transaction. If a caller's
        atomic block is already open, a failed statement has aborted it and no
        further statement can succeed until it unwinds — so the event is
        spooled for replay instead. Closing the connection here would be worse
        than useless: inside an atomic block Django sets ``closed_in_transaction``
        and keeps the dead handle attached, breaking every later query on the
        connection rather than just this one.
        """
        in_caller_transaction = connection.in_atomic_block

        if in_caller_transaction:
            try:
                return append_event(event)
            except DatabaseError as exc:
                logger.error("Spooling audit event (caller transaction aborted): %s", exc)
                _spool(event)
                return None

        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return append_event(event)
            except DatabaseError as exc:
                last_error = exc
                # Safe here: no outer atomic block, so close() detaches the
                # connection and the next attempt opens a fresh one.
                try:
                    connection.close()
                except Exception:  # pragma: no cover
                    pass
                time.sleep(0.05 * (2**attempt))

        logger.error("Spooling audit event after %s failed attempts: %s", attempts, last_error)
        _spool(event)
        return None


def _spool(event: dict) -> None:
    """Persist an unwritable event to disk so nothing is silently lost."""
    try:
        path = spool_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, default=str) + "\n")
    except Exception:  # pragma: no cover
        logger.exception("Failed to spool audit event — event content: %s", event)


def _lock_chain() -> None:
    """Serialise chain appends across every process touching this database."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [CHAIN_LOCK_ID])


@transaction.atomic
def append_event(event: dict) -> AuditEvent:
    """Append one event to the chain. Must run inside a transaction."""
    _lock_chain()

    head = AuditEvent.objects.order_by("-sequence").values("sequence", "hash").first()
    sequence = (head["sequence"] + 1) if head else 1
    previous_hash = head["hash"] if head else GENESIS_HASH

    timestamp = event.get("timestamp") or timezone.now()
    payload = event_payload(
        sequence=sequence,
        timestamp=timestamp,
        actor_id=event.get("actor_id"),
        actor_username=event.get("actor_username") or "system",
        actor_role=event.get("actor_role"),
        entity_type=event.get("entity_type") or "",
        entity_id=str(event.get("entity_id") or ""),
        entity_label=event.get("entity_label") or "",
        action=event.get("action") or "UPDATE",
        changes=event.get("changes") or {},
        reason=event.get("reason"),
        source=event.get("source") or AuditSource.SYSTEM,
        ip_address=event.get("ip_address"),
        user_agent=event.get("user_agent"),
        request_id=event.get("request_id"),
        session_key=event.get("session_key"),
    )
    digest = compute_hash(payload, previous_hash)

    return AuditEvent.objects.create(
        sequence=sequence,
        timestamp=timestamp,
        actor_id=payload["actor_id"],
        actor_username=payload["actor_username"],
        actor_role=payload["actor_role"],
        entity_type=payload["entity_type"],
        entity_id=payload["entity_id"],
        entity_label=payload["entity_label"],
        action=payload["action"],
        changes=payload["changes"],
        reason=payload["reason"],
        source=payload["source"],
        ip_address=payload["ip_address"],
        user_agent=payload["user_agent"],
        request_id=payload["request_id"],
        session_key=payload["session_key"],
        previous_hash=previous_hash,
        hash=digest,
    )


#: Process-wide recorder instance.
recorder = AuditRecorder()


def record(
    *,
    action: str,
    entity_type: str,
    entity_id,
    entity_label: str = "",
    changes: dict | None = None,
    reason: str | None = None,
    context: AuditContext | None = None,
    blocking: bool = False,
    timestamp=None,
) -> AuditEvent | None:
    """Record an audit event using the ambient request context.

    ``blocking=True`` forces a synchronous write — use it for anything whose
    loss would itself be a regulatory finding (signatures, verification,
    release, authentication, configuration changes).
    """
    ctx = context or get_context()
    if not ctx.enabled:
        return None

    event = {
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "entity_label": (entity_label or "")[:255],
        "changes": changes or {},
        "reason": reason or ctx.reason,
        "actor_id": ctx.actor_id,
        "actor_username": ctx.actor_username,
        "actor_role": ctx.actor_role,
        "source": ctx.source,
        "ip_address": ctx.ip_address,
        "user_agent": ctx.user_agent,
        "request_id": ctx.request_id,
        "session_key": ctx.session_key,
        "timestamp": timestamp or timezone.now(),
    }
    return recorder.record(event, blocking=blocking)
