"""Automatic change capture.

Every model in the Dx applications is instrumented, so a developer adding a new
table gets an audit trail without remembering to write one. Field-level diffs
are produced by comparing the in-memory instance against the stored row.
"""
from __future__ import annotations

import logging

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.audit.context import get_context
from apps.audit.recorder import record
from apps.common.constants import AuditAction

logger = logging.getLogger("dx.audit")

#: Applications whose models are captured automatically.
AUDITED_APP_LABELS = {
    "accounts", "patients", "laboratory", "clinical", "quality",
    "inventory", "specialty", "operations", "billing", "reporting",
    "interop", "compliance", "rules", "api",
}

#: Models excluded from automatic capture — either they *are* the trail, or
#: they are high-volume machine state with no evidential value.
EXCLUDED_MODELS = {
    "audit.AuditEvent",
    "audit.ChainCheckpoint",
    "audit.IntegrityAlert",
    "accounts.RecordLock",
    "sessions.Session",
    "admin.LogEntry",
    "contenttypes.ContentType",
    "auth.Permission",
    # Rule firings and webhook attempts are their own evidential records, and
    # both are high-volume: a busy day produces tens of thousands of rows whose
    # content is already retained on the row itself. Capturing them again would
    # bury genuine changes in machine chatter. The *rules* that produced them
    # are audited, which is what an inspector asks about.
    "rules.RuleExecution",
    "api.WebhookDelivery",
}

#: Never written to the trail in clear text.
SENSITIVE_FIELDS = {
    "password", "token", "secret", "api_key", "salt", "secret_hash", "passphrase",
}

#: Events that must not be lost, so they are written synchronously.
BLOCKING_ACTIONS = {
    AuditAction.LOGIN, AuditAction.LOGOUT, AuditAction.DELETE,
    AuditAction.TECHNICAL_VALIDATE, AuditAction.CLINICAL_VERIFY,
    AuditAction.RELEASE, AuditAction.RESTORE,
}


def is_audited(sender) -> bool:
    label = sender._meta.label
    if label in EXCLUDED_MODELS:
        return False
    return sender._meta.app_label in AUDITED_APP_LABELS


def _serialise(instance, field):
    """Render one field value for the trail, masking anything sensitive."""
    if field.name in SENSITIVE_FIELDS or any(s in field.name for s in SENSITIVE_FIELDS):
        return "********"
    if field.is_relation:
        return getattr(instance, field.attname, None)
    value = getattr(instance, field.attname, None)
    if value is None or isinstance(value, (bool, int, float, str, list, dict)):
        return value
    return str(value)


def snapshot(instance) -> dict:
    return {
        field.name: _serialise(instance, field)
        for field in instance._meta.concrete_fields
    }


def label_for(instance) -> str:
    try:
        return str(instance)[:255]
    except Exception:  # pragma: no cover - __str__ may touch unloaded relations
        return f"{instance._meta.object_name}:{instance.pk}"


def warn_about_bulk_operations() -> None:
    """Explain the one hole in automatic capture.

    ``bulk_create``, ``bulk_update`` and ``QuerySet.update`` do not emit model
    signals, so writes made that way produce no audit event. That is a Django
    behaviour, not something this module can intercept. Anything performing a
    bulk write must either record its own summary event (see
    ``manage.py import_legacy``) or wrap the block in ``suppress_auditing()``
    to make the omission deliberate and visible in the code.
    """


@receiver(pre_save)
def capture_previous_state(sender, instance, **kwargs):
    """Stash the stored row so post_save can diff against it."""
    if not is_audited(sender) or instance.pk is None:
        return
    try:
        previous = sender.objects.filter(pk=instance.pk).first()
    except Exception:  # pragma: no cover - table may not exist during migrate
        return
    instance._dx_audit_previous = snapshot(previous) if previous else None


@receiver(post_save)
def capture_save(sender, instance, created, **kwargs):
    """Record a create or update, with a field-level diff.

    The diff comes from the snapshot ``capture_previous_state`` took in
    ``pre_save``; without that there is nothing to compare against, because by
    ``post_save`` the database already holds the new row.

    Note what this does **not** see: ``bulk_create``, ``bulk_update`` and
    ``QuerySet.update`` emit no signals at all. Anything using them must record
    its own summary event or wrap the block in ``suppress_auditing()`` so the
    omission is deliberate and visible.
    """
    if not is_audited(sender) or not get_context().enabled:
        return

    current = snapshot(instance)
    if created:
        action = AuditAction.CREATE
        changes = {name: {"old": None, "new": value} for name, value in current.items()}
    else:
        previous = getattr(instance, "_dx_audit_previous", None)
        if previous is None:
            # Row appeared without a readable predecessor (e.g. loaddata).
            action = AuditAction.CREATE
            changes = {name: {"old": None, "new": value} for name, value in current.items()}
        else:
            action = AuditAction.UPDATE
            changes = {
                name: {"old": previous.get(name), "new": value}
                for name, value in current.items()
                if previous.get(name) != value
            }
            if not changes:
                return  # A save that altered nothing is not an event.

    record(
        action=action,
        entity_type=sender._meta.label,
        entity_id=instance.pk,
        entity_label=label_for(instance),
        changes=changes,
        blocking=action in BLOCKING_ACTIONS,
    )


@receiver(post_delete)
def capture_delete(sender, instance, **kwargs):
    """Record a deletion, including the final state of the row.

    Written synchronously (``blocking``): the row is about to stop existing,
    and an event that never reached the database would leave no trace that it
    ever did.
    """
    if not is_audited(sender) or not get_context().enabled:
        return
    record(
        action=AuditAction.DELETE,
        entity_type=sender._meta.label,
        entity_id=instance.pk,
        entity_label=label_for(instance),
        changes={name: {"old": value, "new": None} for name, value in snapshot(instance).items()},
        blocking=True,
    )


@receiver(m2m_changed)
def capture_m2m(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Record many-to-many edits (e.g. which tests an order contains)."""
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    owner = instance.__class__
    if not is_audited(owner) or not get_context().enabled:
        return

    field_name = sender._meta.db_table.split("_", 1)[-1]
    verb = {"post_add": "added", "post_remove": "removed", "post_clear": "cleared"}[action]
    record(
        action=AuditAction.UPDATE,
        entity_type=owner._meta.label,
        entity_id=instance.pk,
        entity_label=label_for(instance),
        changes={field_name: {"old": None, "new": {verb: sorted(str(pk) for pk in (pk_set or []))}}},
    )


# ── Authentication events ────────────────────────────────────────────────────


@receiver(user_logged_in)
def capture_login(sender, request, user, **kwargs):
    """Record a successful sign-in — 21 CFR Part 11 §11.10(e), §11.300(d)."""
    record(
        action=AuditAction.LOGIN,
        entity_type=get_user_model()._meta.label,
        entity_id=user.pk,
        entity_label=label_for(user),
        changes={},
        blocking=True,
    )


@receiver(user_logged_out)
def capture_logout(sender, request, user, **kwargs):
    """Record a sign-out, including one forced by the idle timeout."""
    if user is None:
        return
    record(
        action=AuditAction.LOGOUT,
        entity_type=get_user_model()._meta.label,
        entity_id=user.pk,
        entity_label=label_for(user),
        changes={},
        blocking=True,
    )


@receiver(user_login_failed)
def capture_login_failure(sender, credentials, request=None, **kwargs):
    """Record a failed sign-in attempt.

    The username is recorded but never the password or any other credential —
    ``credentials`` carries both, and Django's own masking is not relied on.
    """
    """Failed authentication is itself a security-relevant record."""
    username = (credentials or {}).get("username", "unknown")
    record(
        action=AuditAction.LOGIN,
        entity_type="accounts.User",
        entity_id=username,
        entity_label=f"failed login: {username}",
        changes={"outcome": {"old": None, "new": "FAILED"}},
        blocking=True,
    )
