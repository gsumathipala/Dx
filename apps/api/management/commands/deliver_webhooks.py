"""Deliver queued webhook events.

Run from cron or a systemd timer every minute, or with ``--forever`` as a
long-running service. Both are supported because small installations have cron
and large ones have a process supervisor, and neither should have to acquire
the other.
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from apps.api.webhooks import drain


class Command(BaseCommand):
    help = "Deliver pending webhook events to their subscribers."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200,
                            help="Maximum deliveries per pass.")
        parser.add_argument("--forever", action="store_true",
                            help="Keep running, polling every --interval seconds.")
        parser.add_argument("--interval", type=float, default=15.0)

    def handle(self, *args, **options):
        if not options["forever"]:
            self._pass(options["limit"])
            return

        self.stdout.write("Delivering webhooks; Ctrl-C to stop.")
        try:
            while True:
                self._pass(options["limit"])
                time.sleep(options["interval"])
        except KeyboardInterrupt:
            self.stdout.write("Stopped.")

    def _pass(self, limit: int) -> None:
        summary = drain(limit)
        if summary["delivered"] or summary["failed"]:
            self.stdout.write(
                f"delivered={summary['delivered']} failed={summary['failed']}"
            )
