"""Scan for conditions that should be on the exception queue.

Run on a timer (every minute is ample). Idempotent: the queue deduplicates by
source key, so repeated sweeps update rather than multiply.
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from apps.operations.exceptions import sweep


class Command(BaseCommand):
    help = "Raise exception queue items for conditions nobody reported."

    def add_arguments(self, parser):
        parser.add_argument("--forever", action="store_true")
        parser.add_argument("--interval", type=float, default=60.0)

    def handle(self, *args, **options):
        if not options["forever"]:
            self._pass()
            return

        self.stdout.write("Sweeping for exceptions; Ctrl-C to stop.")
        try:
            while True:
                self._pass()
                time.sleep(options["interval"])
        except KeyboardInterrupt:
            self.stdout.write("Stopped.")

    def _pass(self) -> None:
        counts = sweep()
        raised = sum(value for value in counts.values() if value > 0)
        if raised:
            detail = ", ".join(f"{label}: {count}" for label, count in counts.items() if count)
            self.stdout.write(f"{raised} item(s) raised or refreshed — {detail}")
