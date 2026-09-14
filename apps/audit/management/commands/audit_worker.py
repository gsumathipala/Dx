"""Run the audit recorder as a dedicated long-lived process.

    manage.py audit_worker [--verify-interval 3600]

Web workers already run the recorder in-thread; this command exists so a
deployment can additionally run a supervised process that replays anything left
in the spool file and periodically re-verifies the chain, writing a checkpoint
each time. It is the "persistently running" half of the audit subsystem.
"""
from __future__ import annotations

import json
import logging
import signal
import time
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.audit.recorder import append_event, recorder, spool_path
from apps.audit.verification import verify_and_checkpoint

logger = logging.getLogger("dx.audit")


class Command(BaseCommand):
    help = "Run the persistent audit recorder, spool replay and integrity monitor."

    def add_arguments(self, parser):
        parser.add_argument("--verify-interval", type=int, default=3600,
                            help="Seconds between chain verifications (default: 3600; 0 disables).")
        parser.add_argument("--replay-interval", type=int, default=60,
                            help="Seconds between spool replay attempts (default: 60).")

    def handle(self, *args, **options):
        self._stopping = False

        def _stop(signum, frame):
            self.stdout.write("\nShutting down audit worker…")
            self._stopping = True

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        recorder.start()
        self.stdout.write(self.style.SUCCESS("Audit recorder running."))

        verify_interval = options["verify_interval"]
        replay_interval = options["replay_interval"]
        last_verify = 0.0
        last_replay = 0.0

        while not self._stopping:
            now = time.monotonic()

            if replay_interval and now - last_replay >= replay_interval:
                replayed = self.replay_spool()
                if replayed:
                    self.stdout.write(self.style.WARNING(f"Replayed {replayed} spooled event(s)."))
                last_replay = now

            if verify_interval and now - last_verify >= verify_interval:
                result = verify_and_checkpoint()
                style = self.style.SUCCESS if result.ok else self.style.ERROR
                self.stdout.write(style(result.summary))
                last_verify = now

            time.sleep(1)

        recorder.shutdown()
        self.stdout.write(self.style.SUCCESS("Audit worker stopped cleanly."))

    def replay_spool(self) -> int:
        """Re-append events that previously could not be written."""
        path: Path = spool_path()
        if not path.exists() or path.stat().st_size == 0:
            return 0

        working = path.with_suffix(".replaying")
        path.rename(working)

        replayed = 0
        failed: list[str] = []
        with working.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    append_event(json.loads(line))
                    replayed += 1
                except Exception:
                    logger.exception("Failed to replay spooled audit event")
                    failed.append(line)

        if failed:
            with path.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(failed) + "\n")
        working.unlink(missing_ok=True)
        return replayed
