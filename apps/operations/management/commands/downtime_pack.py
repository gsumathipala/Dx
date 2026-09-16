"""Generate the downtime pack.

Run on a timer — every fifteen minutes is reasonable, hourly is the minimum
worth having. A pack generated three weeks ago is worse than no pack, because
people trust it.

    */15 * * * * cd /opt/dx && .venv/bin/python manage.py downtime_pack

The output must end up somewhere reachable when the server is not: a share
replicated to a laboratory workstation, or a USB stick somebody swaps.
"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from apps.operations.continuity import write_pack


class Command(BaseCommand):
    help = "Write a self-contained downtime pack readable with no server."

    def add_arguments(self, parser):
        parser.add_argument("--dir", help="Where to write it. Defaults to DOWNTIME_PACK_DIR.")
        parser.add_argument(
            "--recent-hours", type=int, default=72,
            help="How much result history to include for comparison.",
        )
        parser.add_argument(
            "--passphrase",
            help=(
                "Encrypt the pack. Note the consequence: it then cannot be "
                "read without this application, which is the thing that is "
                "missing when the pack is needed."
            ),
        )
        parser.add_argument("--quiet", action="store_true")

    def handle(self, *args, **options):
        pack = write_pack(
            directory=Path(options["dir"]) if options["dir"] else None,
            passphrase=options.get("passphrase"),
            generated_by="downtime_pack",
            recent_hours=options["recent_hours"],
        )
        if options["quiet"]:
            return

        self.stdout.write(self.style.SUCCESS(f"Downtime pack written to {pack.path}"))
        self.stdout.write(
            f"{pack.order_count} outstanding order(s), {pack.patient_count} patient(s), "
            f"{pack.bytes_written:,} bytes."
        )
        if not pack.encrypted:
            self.stdout.write(self.style.WARNING(
                "The pack is unencrypted patient data on a filesystem. That is "
                "deliberate — a pack you need this application to open is "
                "useless when this application is what is down — but it means "
                "the volume holding it must be encrypted and physically "
                "controlled."
            ))
