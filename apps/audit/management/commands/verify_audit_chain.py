"""Verify the audit hash chain end to end.

    manage.py verify_audit_chain [--from N] [--limit N] [--checkpoint]

Exits non-zero when the chain fails, so it can gate a CI job or a nightly
compliance check.
"""
from __future__ import annotations

import sys

from django.core.management.base import BaseCommand

from apps.audit.verification import verify_and_checkpoint, verify_chain


class Command(BaseCommand):
    help = "Verify the integrity of the immutable audit trail."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="start", type=int, default=1,
                            help="First sequence number to verify (default: 1).")
        parser.add_argument("--limit", type=int, default=None,
                            help="Stop after this many events.")
        parser.add_argument("--checkpoint", action="store_true",
                            help="Record a chain checkpoint and raise an alert on failure.")

    def handle(self, *args, **options):
        if options["checkpoint"]:
            result = verify_and_checkpoint()
        else:
            result = verify_chain(start=options["start"], limit=options["limit"])

        if result.ok:
            self.stdout.write(self.style.SUCCESS(result.summary))
            return

        self.stdout.write(self.style.ERROR(result.summary))
        for problem in result.problems:
            self.stdout.write(self.style.ERROR(f"  • {problem}"))
        sys.exit(1)
