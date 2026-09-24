"""Reset the installer account's password from the command line.

    manage.py reset_installer_password

The installer's password cannot be reset through the web interface — an
administrator who could do so would hold the installer's authority, and the
separation of duties would be theatre. Recovery therefore requires shell access
to the server, which is a deliberate and higher bar.

The reset is recorded in the audit trail like any other.
"""
from __future__ import annotations

import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.audit.context import audit_as
from apps.audit.models import AuditSource
from apps.audit.recorder import record, recorder
from apps.common.constants import AuditAction, Role

User = get_user_model()


class Command(BaseCommand):
    help = "Reset the installer account's password (requires shell access)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="",
                            help="Which installer account, if more than one exists.")
        parser.add_argument("--password", default="",
                            help="Prompted for interactively if omitted.")
        parser.add_argument("--reason", default="",
                            help="Recorded in the audit trail.")

    def handle(self, *args, **options):
        """Reset the installer's password from a shell.

        The only route back in when the installer password is lost. It requires
        shell access on the server deliberately: an administrator who could
        reset it through a screen would simply *become* the installer, and the
        separation of duties the role exists for would be worth nothing.
        """
        accounts = User.objects.filter(role=Role.INSTALLER)
        if options["username"]:
            accounts = accounts.filter(username=options["username"])

        count = accounts.count()
        if count == 0:
            raise CommandError(
                "No installer account exists. Create one with `manage.py create_installer`."
            )
        if count > 1:
            names = ", ".join(accounts.values_list("username", flat=True))
            raise CommandError(f"Several installer accounts exist ({names}). Name one with --username.")

        user = accounts.get()
        password = options["password"] or self._prompt_password(user)

        with audit_as(actor_username="reset_installer_password",
                      actor_role=Role.INSTALLER, source=AuditSource.CLI):
            user.set_password(password)
            user.is_active = True
            user.save(update_fields=["password", "is_active"])

            from apps.compliance.services import record_password_change, security_state

            record_password_change(user)
            state = security_state(user)
            state.failed_attempts = 0
            state.locked_until = None
            state.save(update_fields=["failed_attempts", "locked_until"])

            record(
                action=AuditAction.UPDATE,
                entity_type="accounts.User",
                entity_id=user.pk,
                entity_label=f"installer password reset from the command line: {user.username}",
                changes={"password": {"old": "********", "new": "********"}},
                reason=options["reason"] or "Recovery via manage.py reset_installer_password",
                blocking=True,
            )
        recorder.flush(timeout=10)

        self.stdout.write(self.style.SUCCESS(
            f"Password reset for installer account {user.username!r}, and the account re-enabled."
        ))

    def _prompt_password(self, user) -> str:
        while True:
            password = getpass.getpass(f"New password for {user.username}: ")
            if password != getpass.getpass("Password (again): "):
                self.stderr.write("Passwords do not match.")
                continue
            try:
                validate_password(password, user)
            except ValidationError as error:
                for message in error.messages:
                    self.stderr.write(f"  {message}")
                continue
            return password
