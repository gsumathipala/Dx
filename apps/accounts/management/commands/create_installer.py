"""Create the installer account used to commission a new installation.

    manage.py create_installer --username installer

The installer holds the highest system authority — user administration,
configuration, instrument interfaces, maintenance and the database reset — and
no clinical authority whatsoever. It cannot open a patient record, an order, a
result or a report, and that is enforced by ``apps.accounts.phi_barrier``
rather than by leaving the links out of the menu.

This exists so a fresh database can be brought up without ``createsuperuser``,
which would produce a Django superuser with unrestricted access.
"""
from __future__ import annotations

import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.audit.context import audit_as
from apps.audit.models import AuditSource
from apps.common.constants import Role

User = get_user_model()


class Command(BaseCommand):
    help = "Create an installer account (system authority, no clinical access)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="installer")
        parser.add_argument("--name", default="System Installer")
        parser.add_argument("--email", default="")
        parser.add_argument(
            "--password", default="",
            help="Prompted for interactively if omitted. Avoid on a shared machine: "
                 "a password given on the command line lands in the shell history.",
        )
        parser.add_argument(
            "--django-admin", action="store_true",
            help="Also grant access to the Django admin site. Off by default — "
                 "the Django admin bypasses the PHI barrier.",
        )

    def handle(self, *args, **options):
        """Create the single permanent installer account.

        Only creatable here, never through the web interface: the account that
        can wipe the database and administer every other account should not be
        reachable by anybody who has merely compromised a browser session.
        """
        username = options["username"].strip()
        if not username:
            raise CommandError("A username is required.")

        if User.objects.filter(username=username).exists():
            raise CommandError(
                f"A user named {username!r} already exists. Choose another name, "
                "or reset that account's password rather than creating a duplicate."
            )

        password = options["password"] or self._prompt_password()

        with audit_as(actor_username="create_installer", actor_role=Role.INSTALLER,
                      source=AuditSource.CLI):
            user = User.objects.create_user(
                username=username,
                password=password,
                name=options["name"],
                email=options["email"] or None,
                role=Role.INSTALLER,
                # The Django admin has no concept of the PHI barrier, so an
                # installer is kept out of it unless explicitly asked for.
                is_staff=options["django_admin"],
                is_superuser=False,
            )

            from apps.compliance.services import record_password_change

            record_password_change(user)

        self.stdout.write(self.style.SUCCESS(f"Created installer account {username!r}."))
        self.stdout.write(
            "This account can administer users, configuration, interfaces and "
            "maintenance, and can reset the database.\n"
            "It cannot open patients, orders, results or reports — that barrier is "
            "enforced on every request, not just hidden from the menu."
        )
        if options["django_admin"]:
            self.stdout.write(self.style.WARNING(
                "Django admin access was granted. The Django admin does not apply "
                "the PHI barrier, so this account can reach patient tables through "
                "it. Grant it only for commissioning, and revoke it afterwards."
            ))

    def _prompt_password(self) -> str:
        while True:
            password = getpass.getpass("Password: ")
            if password != getpass.getpass("Password (again): "):
                self.stderr.write("Passwords do not match.")
                continue
            try:
                validate_password(password)
            except ValidationError as error:
                for message in error.messages:
                    self.stderr.write(f"  {message}")
                continue
            return password
