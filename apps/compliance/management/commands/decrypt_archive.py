"""Decrypt a Dx encrypted archive.

    manage.py decrypt_archive backup.jsonl.dx --out backup.jsonl

Reads anything written with AES-256-GCM by `reset_data --encrypt-archive` or
`apps.compliance.encryption.encrypt_file`. The passphrase is prompted for
rather than passed on the command line, which would put it in shell history.
"""
from __future__ import annotations

import getpass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.compliance.encryption import EncryptionError, decrypt_file, is_encrypted


class Command(BaseCommand):
    help = "Decrypt a Dx encrypted archive."

    def add_arguments(self, parser):
        parser.add_argument("source", help="The encrypted file.")
        parser.add_argument("--out", default="", help="Where to write the plaintext.")
        parser.add_argument("--passphrase", default="",
                            help="Prompted for if omitted. Avoid: it lands in shell history.")

    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.exists():
            raise CommandError(f"No such file: {source}")
        if not is_encrypted(source):
            raise CommandError(f"{source} is not a Dx encrypted archive.")

        destination = Path(options["out"]) if options["out"] else source.with_suffix("")
        passphrase = options["passphrase"] or getpass.getpass("Passphrase: ")

        try:
            decrypt_file(source, destination, passphrase)
        except EncryptionError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS(f"Decrypted to {destination}"))
