"""Install and remove the append-only protection.

Removing the triggers is a deliberate, logged act. It exists because two
legitimate operations require it — restoring a database from backup, and
tearing down a test database — and because pretending otherwise would only
lead someone to disable them ad hoc and forget to put them back.
"""
from __future__ import annotations

import contextlib
import logging

from django.db import connection

from apps.audit import sql

logger = logging.getLogger("dx.audit")


def _run(statements: str, using=connection) -> None:
    if using.vendor != "postgresql":
        return
    with using.cursor() as cursor:
        cursor.execute(statements)


def install(using=connection) -> None:
    """(Re)create the append-only triggers."""
    _run(sql.FORBID_FUNCTION, using)
    _run(sql.CREATE_TRIGGERS, using)
    _run(sql.CREATE_SIGNATURE_TRIGGERS, using)


def remove(using=connection) -> None:
    """Drop the append-only triggers. Always pair with ``install``."""
    _run(sql.DROP_TRIGGERS, using)
    _run(sql.DROP_SIGNATURE_TRIGGERS, using)


def is_installed(using=connection) -> bool:
    if using.vendor != "postgresql":
        return False
    with using.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_trigger WHERE tgname IN "
            "('dx_audit_no_update', 'dx_audit_no_delete', 'dx_audit_no_truncate')"
        )
        return cursor.fetchone()[0] == 3


@contextlib.contextmanager
def unprotected(using=connection, *, reason: str = "maintenance"):
    """Temporarily lift the protection, restoring it even on error."""
    logger.warning("Audit append-only protection lifted: %s", reason)
    remove(using)
    try:
        yield
    finally:
        install(using)
        logger.warning("Audit append-only protection restored")
