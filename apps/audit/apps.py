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
