"""AES-256-GCM archive encryption."""
from __future__ import annotations

import secrets
import tempfile
from pathlib import Path

from django.test import TestCase

from apps.compliance.encryption import (
    EncryptionError, IntegrityError, decrypt_bytes, decrypt_file,
    encrypt_bytes, encrypt_file, is_encrypted,
)

PASSPHRASE = "correct horse battery staple"


class EncryptBytesTests(TestCase):
    def setUp(self):
        self.plaintext = b"PID|1||MRN-0001||Doe^Jane||19800101|F" * 40

    def test_round_trip(self):
        sealed = encrypt_bytes(self.plaintext, PASSPHRASE)
        self.assertEqual(decrypt_bytes(sealed, PASSPHRASE), self.plaintext)

    def test_plaintext_is_not_present_in_the_ciphertext(self):
        sealed = encrypt_bytes(self.plaintext, PASSPHRASE)
        self.assertNotIn(b"MRN-0001", sealed)
        self.assertNotIn(b"Doe", sealed)

    def test_wrong_passphrase_is_refused(self):
        sealed = encrypt_bytes(self.plaintext, PASSPHRASE)
        with self.assertRaises(IntegrityError):
            decrypt_bytes(sealed, "wrong")

    def test_tampering_is_detected(self):
        sealed = bytearray(encrypt_bytes(self.plaintext, PASSPHRASE))
        sealed[-1] ^= 0x01
        with self.assertRaises(IntegrityError):
            decrypt_bytes(bytes(sealed), PASSPHRASE)

    def test_tampering_with_the_header_is_detected(self):
        """The header is authenticated, not merely read."""
        sealed = bytearray(encrypt_bytes(self.plaintext, PASSPHRASE))
        sealed[20] ^= 0x01  # inside the salt
        with self.assertRaises(IntegrityError):
            decrypt_bytes(bytes(sealed), PASSPHRASE)

    def test_each_encryption_differs(self):
        """A fresh salt and nonce every time, so identical inputs differ."""
        first = encrypt_bytes(self.plaintext, PASSPHRASE)
        second = encrypt_bytes(self.plaintext, PASSPHRASE)
        self.assertNotEqual(first, second)
        self.assertEqual(decrypt_bytes(first, PASSPHRASE),
                         decrypt_bytes(second, PASSPHRASE))

    def test_a_foreign_file_is_rejected_clearly(self):
        with self.assertRaises(EncryptionError):
            decrypt_bytes(b"this is not an archive at all, not even close", PASSPHRASE)

    def test_an_empty_passphrase_is_refused(self):
        with self.assertRaises(EncryptionError):
            encrypt_bytes(self.plaintext, "")


class EncryptFileTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.source = self.dir / "backup.dump"
        # Larger than one chunk, so the streaming path is exercised.
        self.source.write_bytes(secrets.token_bytes(200 * 1024))

    def test_round_trip_is_byte_exact(self):
        sealed = encrypt_file(self.source, self.dir / "backup.dx", PASSPHRASE)
        restored = decrypt_file(sealed, self.dir / "restored.dump", PASSPHRASE)
        self.assertEqual(restored.read_bytes(), self.source.read_bytes())

    def test_the_header_is_recognisable(self):
        sealed = encrypt_file(self.source, self.dir / "backup.dx", PASSPHRASE)
        self.assertTrue(is_encrypted(sealed))
        self.assertFalse(is_encrypted(self.source))

    def test_wrong_passphrase_is_refused(self):
        sealed = encrypt_file(self.source, self.dir / "backup.dx", PASSPHRASE)
        with self.assertRaises(IntegrityError):
            decrypt_file(sealed, self.dir / "restored.dump", "wrong")

    def test_truncation_is_detected(self):
        sealed = encrypt_file(self.source, self.dir / "backup.dx", PASSPHRASE)
        truncated = self.dir / "truncated.dx"
        truncated.write_bytes(sealed.read_bytes()[:-500])
        with self.assertRaises(IntegrityError):
            decrypt_file(truncated, self.dir / "restored.dump", PASSPHRASE)

    def test_a_failed_decryption_leaves_no_partial_file(self):
        """A half-written 'restored' backup would be worse than none."""
        sealed = encrypt_file(self.source, self.dir / "backup.dx", PASSPHRASE)
        destination = self.dir / "restored.dump"
        with self.assertRaises(IntegrityError):
            decrypt_file(sealed, destination, "wrong")
        self.assertFalse(destination.exists())
        self.assertFalse(destination.with_suffix(".dump.partial").exists())


class EncryptedAuditArchiveTests(TestCase):
    """`reset_data --encrypt-archive` must leave nothing readable behind."""

    def setUp(self):
        from tests.factories import make_patient

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        make_patient(mrn="MRN-ENCRYPT")

        from apps.audit.recorder import recorder

        recorder.flush(timeout=5)

    def test_the_archive_is_encrypted_and_readable_back(self):
        from django.core.management import call_command

        call_command(
            "reset_data", confirm="ERASE ALL DATA", archive_to=self.tmp.name,
            encrypt_archive=PASSPHRASE, force_production=True, verbosity=0,
        )

        archives = list(Path(self.tmp.name).glob("*.dx"))
        self.assertEqual(len(archives), 1, "expected exactly one encrypted archive")
        self.assertFalse(list(Path(self.tmp.name).glob("*.jsonl")),
                         "the plaintext archive must not survive")

        self.assertNotIn(b"MRN-ENCRYPT", archives[0].read_bytes())

        restored = decrypt_file(archives[0], Path(self.tmp.name) / "out.jsonl", PASSPHRASE)
        self.assertIn("MRN-ENCRYPT", restored.read_text())
