"""The immutable audit trail, and the thread that writes it.

This AppConfig is where the recorder thread is started, which makes it one of
the few places in the project where import order and process lifecycle
genuinely matter — see ``_should_start_recorder``.
"""
from __future__ import annotations

import os
import sys

from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    label = "audit"
    verbose_name = "Audit trail"

    def ready(self) -> None:
        # Connect the automatic capture signals.
        from apps.audit import signals  # noqa: F401

        # Start the persistent recorder thread, except for commands where a
        # background writer would be wrong or actively harmful.
        if self._should_start_recorder():
            from apps.audit.recorder import recorder

            recorder.start()

    @staticmethod
    def _should_start_recorder() -> bool:
        """Whether this process should run a background audit writer.

        Three situations where it must not, each learned the hard way:

        * **Schema and shell commands.** ``migrate`` runs before the audit
          tables necessarily exist, and a recorder that starts mid-migration
          writes into a half-built schema.
        * **Tests.** The test runner needs synchronous, deterministic writes;
          a background thread makes assertions race. ``config/test_runner.py``
          also drops the append-only triggers, which the recorder would fight.
        * **The autoreloader's parent.** ``runserver`` forks, and without this
          check two recorder threads append to one chain from two processes.

        ``DX_AUDIT_RECORDER=0`` forces it off for anything not listed.
        """
        if os.environ.get("DX_AUDIT_RECORDER", "").lower() in {"0", "off", "false"}:
            return False
        argv = sys.argv
        if len(argv) > 1:
            command = argv[1]
            if command in {
                "migrate", "makemigrations", "collectstatic", "test",
                "shell", "dbshell", "showmigrations", "sqlmigrate",
                "verify_audit_chain", "audit_worker",
            }:
                return False
        # Avoid a duplicate thread in the autoreloader's parent process.
        if os.environ.get("RUN_MAIN") == "false":
            return False
        return True
