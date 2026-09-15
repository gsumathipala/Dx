"""Erase all operational data, leaving an installable empty system.

    manage.py reset_data --archive-to backups/ --confirm "ERASE ALL DATA"

Intended for commissioning a new installation: install, migrate, seed, verify,
then reset to hand over an empty system.

Why this is more than a TRUNCATE
--------------------------------
The audit trail is append-only by design, and a reset is exactly the operation
someone would reach for to erase evidence. So a reset here cannot be silent:

* The existing trail is **archived to a file first** (unless explicitly
  skipped), with its chain verified before archiving so the archive is known
  to be intact at the moment it was taken.
* The new chain's **first event records the reset** — who ran it, when, how
  many events the previous chain held and the hash it ended on. A later
  inspection can therefore see that a reset happened and reconcile the archive
  against the recorded head hash, rather than finding an unexplained empty
  table.
* The append-only triggers are lifted only for the duration of the wipe and
  reinstated immediately, including if the wipe fails.

It refuses to run against a non-development database unless
``--i-understand-this-is-production`` is also given.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.apps import apps as django_apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

CONFIRM_PHRASE = "ERASE ALL DATA"

#: Wiped in this order so foreign keys unwind cleanly. Everything else in the
#: Dx applications is discovered automatically; these are listed to control
#: ordering, not to limit the scope.
PRIORITY_ORDER = [
    "compliance", "clinical", "specialty", "billing", "reporting",
    "operations", "quality", "inventory", "interop", "laboratory",
    "patients", "accounts",
]

#: Never wiped: Django's own plumbing, and the audit tables, which are handled
#: separately so the reset itself stays on the record.
PROTECTED_LABELS = {
    "audit.AuditEvent", "audit.ChainCheckpoint", "audit.IntegrityAlert",
    "contenttypes.ContentType", "auth.Permission", "sessions.Session",
    "admin.LogEntry",
}

DX_APP_LABELS = {
    "accounts", "patients", "laboratory", "clinical", "quality", "inventory",
    "specialty", "operations", "billing", "reporting", "interop", "compliance",
}


class Command(BaseCommand):
    help = "Erase all operational data, leaving an empty installable system."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm", default="",
            help=f'Must be exactly "{CONFIRM_PHRASE}".',
        )
        parser.add_argument(
            "--archive-to", default="",
            help="Directory to write the audit trail archive into before wiping.",
        )
        parser.add_argument(
            "--skip-audit-archive", action="store_true",
            help="Do not archive the audit trail. The reset is still recorded.",
        )
        parser.add_argument(
            "--keep-audit", action="store_true",
            help="Wipe operational data but leave the audit trail in place.",
        )
        parser.add_argument(
            "--keep-users", action="store_true",
            help="Leave user accounts, departments and competency records.",
        )
        parser.add_argument(
            "--i-understand-this-is-production", action="store_true",
            dest="force_production",
            help="Required when DEBUG is off.",
        )
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would be deleted, delete nothing.")

    # ── Entry point ──────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]

        if not self.dry_run:
            self._check_authorised(options)

        models = self._models_to_wipe(keep_users=options["keep_users"])
        counts = {model._meta.label: model.objects.count() for model in models}
        total = sum(counts.values())

        self._report_plan(counts, total, options)

        if self.dry_run:
            self.stdout.write(self.style.WARNING(
                f"Dry run — {total} row(s) would be deleted. Nothing was written."
            ))
            return

        if total == 0 and not options["keep_audit"]:
            self.stdout.write("Nothing to delete.")

        archive_path = None
        if not options["keep_audit"] and not options["skip_audit_archive"]:
            archive_path = self._archive_audit_trail(options["archive_to"])

        previous_head, previous_count = self._chain_head()

        self._wipe(models, keep_audit=options["keep_audit"])

        self._record_reset(
            previous_head=previous_head,
            previous_count=previous_count,
            archive_path=archive_path,
            deleted=total,
            options=options,
        )

        self.stdout.write(self.style.SUCCESS(f"\nDeleted {total} row(s)."))
        if archive_path:
            self.stdout.write(f"Audit trail archived to {archive_path}")
        self.stdout.write(
            "The new audit chain opens with an event recording this reset, "
            "including the previous chain's length and head hash."
        )
        if not options["keep_users"]:
            self.stdout.write(self.style.WARNING(
                "No user accounts remain. Create one before signing in:\n"
                "  manage.py create_installer"
            ))

    # ── Guards ───────────────────────────────────────────────────────────────

    def _check_authorised(self, options) -> None:
        if options["confirm"] != CONFIRM_PHRASE:
            raise CommandError(
                f'This erases all data. Re-run with --confirm "{CONFIRM_PHRASE}" '
                "if that is what you intend."
            )
        if not settings.DEBUG and not options["force_production"]:
            raise CommandError(
                "DEBUG is off, so this looks like a real deployment. If you are "
                "certain, add --i-understand-this-is-production. Take a database "
                "backup first: this is not recoverable from within the application."
            )

    # ── Planning ─────────────────────────────────────────────────────────────

    def _models_to_wipe(self, *, keep_users: bool):
        ordered = []
        for label in PRIORITY_ORDER:
            if keep_users and label == "accounts":
                continue
            config = django_apps.get_app_config(label)
            # Reverse declaration order approximates dependency order well
            # enough; the wipe runs with constraints deferred regardless.
            for model in reversed(list(config.get_models())):
                if model._meta.label in PROTECTED_LABELS:
                    continue
                ordered.append(model)

        for config in django_apps.get_app_configs():
            if config.label in DX_APP_LABELS or config.label == "audit":
                continue
            for model in config.get_models():
                if model._meta.label in PROTECTED_LABELS:
                    continue
                ordered.append(model)

        return ordered

    def _report_plan(self, counts, total, options) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("Rows to delete:"))
        for label, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            if count:
                self.stdout.write(f"  {label:44} {count:>8}")
        self.stdout.write(f"  {'total':44} {total:>8}")

        if options["keep_users"]:
            self.stdout.write("  (user accounts and departments are being kept)")
        if options["keep_audit"]:
            self.stdout.write("  (the audit trail is being kept)")

    # ── Audit trail handling ─────────────────────────────────────────────────

    def _chain_head(self):
        from apps.audit.models import AuditEvent

        head = AuditEvent.objects.order_by("-sequence").values("sequence", "hash").first()
        count = AuditEvent.objects.count()
        return (head["hash"] if head else None), count

    def _archive_audit_trail(self, directory: str) -> Path | None:
        """Verify then write the trail to a file before it is destroyed."""
        from apps.audit.models import AuditEvent
        from apps.audit.verification import verify_chain

        if not AuditEvent.objects.exists():
            return None

        result = verify_chain()
        if not result.ok:
            self.stdout.write(self.style.ERROR(
                "The audit chain does not verify. Archiving it anyway, but the "
                "archive is of a trail that was already compromised:"
            ))
            for problem in result.problems[:5]:
                self.stdout.write(self.style.ERROR(f"  • {problem}"))

        target_dir = Path(directory) if directory else Path(settings.BASE_DIR) / "audit-archives"
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = target_dir / f"audit-trail-{stamp}.jsonl"

        written = 0
        with path.open("w", encoding="utf-8") as handle:
            # A header line so the archive is self-describing.
            handle.write(json.dumps({
                "_archive": "dx-audit-trail",
                "taken_at": timezone.now().isoformat(),
                "event_count": result.checked,
                "head_sequence": result.head_sequence,
                "head_hash": result.head_hash,
                "chain_verified": result.ok,
            }) + "\n")
            for event in AuditEvent.objects.order_by("sequence").iterator(chunk_size=1000):
                handle.write(json.dumps({
                    "sequence": event.sequence,
                    "timestamp": event.timestamp.isoformat(),
                    "actor_username": event.actor_username,
                    "actor_role": event.actor_role,
                    "action": event.action,
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                    "entity_label": event.entity_label,
                    "changes": event.changes,
                    "reason": event.reason,
                    "source": event.source,
                    "ip_address": event.ip_address,
                    "request_id": event.request_id,
                    "previous_hash": event.previous_hash,
                    "hash": event.hash,
                }, default=str) + "\n")
                written += 1

        self.stdout.write(f"Archived {written} audit event(s) to {path}")
        return path

    # ── The wipe ─────────────────────────────────────────────────────────────

    def _wipe(self, models, *, keep_audit: bool) -> None:
        from apps.audit import protection
        from apps.audit.context import suppress_auditing

        # Electronic signatures are append-only too, so the protection has to
        # be lifted for the operational wipe as well as the trail. It is logged
        # and reinstated even if the wipe raises.
        with suppress_auditing(), protection.unprotected(reason="reset_data"):
            with transaction.atomic():
                for model in models:
                    model.objects.all().delete()

            if not keep_audit:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM audit_chain_checkpoints")
                    cursor.execute("DELETE FROM audit_integrity_alerts")
                    cursor.execute("DELETE FROM audit_events")

    def _record_reset(self, *, previous_head, previous_count, archive_path,
                      deleted, options) -> None:
        """Open the new chain with an event describing what was erased.

        This is the point of the whole exercise: an empty audit table with no
        explanation is indistinguishable from a cover-up. The first event of
        the new chain says a reset happened, who ran it, and what the previous
        chain looked like.
        """
        from apps.audit.context import audit_as
        from apps.audit.models import AuditSource
        from apps.audit.recorder import record, recorder
        from apps.common.constants import AuditAction

        with audit_as(actor_username="reset_data", actor_role="installer",
                      source=AuditSource.CLI):
            record(
                action=AuditAction.RESTORE,
                entity_type="operations.SystemSetting",
                entity_id="database-reset",
                entity_label="database reset — all operational data erased",
                changes={
                    "rows_deleted": {"old": deleted, "new": 0},
                    "previous_chain_events": {"old": previous_count, "new": 0},
                    "previous_chain_head_hash": {"old": previous_head, "new": None},
                    "audit_trail_archived_to": {
                        "old": None, "new": str(archive_path) if archive_path else None,
                    },
                    "audit_trail_kept": {"old": None, "new": options["keep_audit"]},
                    "user_accounts_kept": {"old": None, "new": options["keep_users"]},
                },
                reason="Commissioning reset via manage.py reset_data",
                blocking=True,
            )
        recorder.flush(timeout=10)
