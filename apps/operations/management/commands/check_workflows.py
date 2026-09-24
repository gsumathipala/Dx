"""Check the whole installation for self-consistency.

The test suite proves each piece behaves correctly. This asks whether the data
in *this* installation currently contradicts itself — a completed order with an
unverified analyte, an analyte approved for autoverification with no QC target,
a bidirectional interface that answers analysers in a vocabulary they do not
speak.

Exits non-zero when anything at ERROR is found, so a nightly job can gate on
it. Run it after an upgrade, after a data migration, and before an inspection.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.operations.integrity import ERROR, INFO, WARN, run_all, summarise


class Command(BaseCommand):
    help = "Check every workflow for self-consistency. Non-zero exit on ERROR."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json", action="store_true",
            help="Machine-readable output, for a monitoring job.",
        )
        parser.add_argument(
            "--quiet", action="store_true",
            help="Print only errors and warnings.",
        )
        parser.add_argument(
            "--fail-on", choices=["error", "warn", "never"], default="error",
            help="What makes the exit status non-zero. Default: error.",
        )

    def handle(self, *args, **options):
        """Run every check and report. Exit status is set by ``--fail-on``.

        ``SystemExit`` rather than ``CommandError`` because the exit code is
        the interface here: this is designed to gate a nightly job, and a
        traceback on a finding would be noise.
        """
        findings, failures = run_all()
        counts = summarise(findings)

        if options["json"]:
            self.stdout.write(json.dumps({
                "counts": counts,
                "checks_failed": failures,
                "findings": [
                    {
                        "code": f.code, "severity": f.severity, "title": f.title,
                        "detail": f.detail, "count": f.count, "examples": f.examples,
                    }
                    for f in findings
                ],
            }, indent=2))
        else:
            self._report(findings, options["quiet"])

        threshold = options["fail_on"]
        if threshold == "error" and counts.get(ERROR):
            raise SystemExit(1)
        if threshold == "warn" and (counts.get(ERROR) or counts.get(WARN)):
            raise SystemExit(1)

    def _report(self, findings, quiet: bool) -> None:
        """Print findings worst-first, so the important ones are not scrolled past."""
        styles = {
            ERROR: self.style.ERROR,
            WARN: self.style.WARNING,
            INFO: self.style.SUCCESS,
        }
        order = {ERROR: 0, WARN: 1, INFO: 2}

        shown = 0
        for finding in sorted(findings, key=lambda f: (order[f.severity], f.code)):
            if quiet and finding.severity == INFO:
                continue
            shown += 1
            style = styles[finding.severity]
            self.stdout.write(style(f"\n{finding.severity}  {finding.code}"))
            self.stdout.write(f"  {finding.title}")
            if finding.count > 1:
                self.stdout.write(f"  {finding.count} affected")
            if finding.detail:
                self.stdout.write(f"  {finding.detail}")
            for example in finding.examples:
                self.stdout.write(f"    · {example}")

        counts = summarise(findings)
        self.stdout.write("")
        if counts[ERROR]:
            self.stdout.write(self.style.ERROR(
                f"{counts[ERROR]} error(s), {counts[WARN]} warning(s). "
                "Errors mean the data contradicts itself — somebody must look."
            ))
        elif counts[WARN]:
            self.stdout.write(self.style.WARNING(
                f"No errors. {counts[WARN]} warning(s)."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "Every workflow is self-consistent."
            ))
        if not shown:
            self.stdout.write("Nothing to report.")
