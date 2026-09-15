"""The commissioning reset: safeguards, archival and the record it leaves."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.audit.models import AuditEvent
from apps.audit.recorder import recorder
from apps.laboratory.models import Order
from apps.patients.models import Patient
from tests.factories import make_order, make_patient, make_test, make_user


class ResetSafeguardTests(TestCase):
    def test_refuses_without_the_confirmation_phrase(self):
        with self.assertRaises(CommandError) as ctx:
            call_command("reset_data", verbosity=0)
        self.assertIn("ERASE ALL DATA", str(ctx.exception))

    def test_refuses_a_wrong_confirmation_phrase(self):
        with self.assertRaises(CommandError):
            call_command("reset_data", confirm="erase all data", verbosity=0)

    @override_settings(DEBUG=False)
    def test_refuses_when_debug_is_off_without_the_production_flag(self):
        with self.assertRaises(CommandError) as ctx:
            call_command("reset_data", confirm="ERASE ALL DATA", verbosity=0)
        self.assertIn("production", str(ctx.exception))

    def test_dry_run_deletes_nothing(self):
        make_patient(mrn="MRN-DRY")
        call_command("reset_data", dry_run=True, verbosity=0)
        self.assertTrue(Patient.objects.filter(mrn="MRN-DRY").exists())


class ResetBehaviourTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.user = make_user("reset-tech")
        self.test = make_test(code="RST")
        patient = make_patient(mrn="MRN-RESET")
        make_order(patient, [self.test])
        recorder.flush(timeout=5)

    def _reset(self, **kwargs):
        # Django runs tests with DEBUG off, so the production guard applies and
        # has to be answered explicitly — which is the guard doing its job.
        options = {"confirm": "ERASE ALL DATA", "archive_to": self.tmp.name,
                   "force_production": True, "verbosity": 0}
        options.update(kwargs)
        call_command("reset_data", **options)
        recorder.flush(timeout=5)

    def test_operational_data_is_erased(self):
        self._reset()
        self.assertEqual(Patient.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)

    def test_the_new_chain_records_the_reset(self):
        previous_count = AuditEvent.objects.count()
        head = AuditEvent.objects.order_by("-sequence").first().hash

        self._reset()

        self.assertEqual(AuditEvent.objects.count(), 1)
        event = AuditEvent.objects.get()
        self.assertEqual(event.sequence, 1)
        self.assertIn("database reset", event.entity_label)
        self.assertEqual(event.changes["previous_chain_events"]["old"], previous_count)
        self.assertEqual(event.changes["previous_chain_head_hash"]["old"], head)

    def test_the_trail_is_archived_before_it_is_erased(self):
        expected = AuditEvent.objects.count()
        self._reset()

        archives = list(Path(self.tmp.name).glob("audit-trail-*.jsonl"))
        self.assertEqual(len(archives), 1)

        lines = archives[0].read_text().strip().splitlines()
        header = json.loads(lines[0])
        self.assertEqual(header["_archive"], "dx-audit-trail")
        self.assertTrue(header["chain_verified"])
        self.assertEqual(header["event_count"], expected)
        self.assertEqual(len(lines) - 1, expected)

    def test_the_archive_reconciles_with_the_new_chains_first_event(self):
        """The archive's head hash must match what the reset recorded."""
        self._reset()
        archive = next(Path(self.tmp.name).glob("audit-trail-*.jsonl"))
        header = json.loads(archive.read_text().splitlines()[0])
        event = AuditEvent.objects.get()
        self.assertEqual(
            header["head_hash"], event.changes["previous_chain_head_hash"]["old"]
        )

    def test_append_only_protection_is_reinstated(self):
        from apps.audit import protection

        self._reset()
        self.assertTrue(protection.is_installed())

    def test_the_chain_verifies_after_a_reset(self):
        from apps.audit.verification import verify_chain

        self._reset()
        self.assertTrue(verify_chain().ok)

    def test_keep_users_leaves_accounts_in_place(self):
        self._reset(keep_users=True)
        from django.contrib.auth import get_user_model

        self.assertTrue(get_user_model().objects.filter(username="reset-tech").exists())
        self.assertEqual(Patient.objects.count(), 0)

    def test_keep_audit_leaves_the_trail_in_place(self):
        before = AuditEvent.objects.count()
        self._reset(keep_audit=True)
        self.assertGreaterEqual(AuditEvent.objects.count(), before)
        self.assertEqual(Patient.objects.count(), 0)
