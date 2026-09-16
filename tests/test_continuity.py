"""Business continuity: downtime records, the pack, read-only mode, backloading.

The backload tests carry the weight. A retrospective result that names the
typist instead of the person who performed the test is false attribution on a
clinical record, and it is the first thing an inspector checks after an outage.
"""
from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.common.constants import OrderStatus
from apps.compliance.services import ControlViolation
from apps.laboratory.models import Result
from apps.operations import continuity
from apps.operations.models import DowntimeEvent, DowntimePack, ExceptionItem
from tests.factories import make_order, make_patient, make_test, make_user

PASSWORD = "Str0ng-Pass!23"


class DeclarationTests(TestCase):
    def setUp(self):
        self.manager = make_user("mgr", role="manager", password=PASSWORD)

    def test_references_are_sequential_within_the_year(self):
        first = continuity.declare(kind="unplanned", reason="Power loss", user=self.manager)
        second = continuity.declare(kind="planned", reason="Upgrade", user=self.manager)
        year = timezone.now().year
        self.assertEqual(first.reference, f"DT-{year}-0001")
        self.assertEqual(second.reference, f"DT-{year}-0002")

    def test_the_outage_can_be_backdated_to_when_it_started(self):
        began = timezone.now() - timedelta(hours=3)
        event = continuity.declare(
            kind="unplanned", reason="Noticed at handover", user=self.manager,
            began_at=began,
        )
        self.assertEqual(event.began_at, began)
        self.assertGreater(event.declared_at, event.began_at)
        self.assertAlmostEqual(event.duration_hours, 3.0, places=1)

    def test_declaring_is_audited(self):
        event = continuity.declare(kind="unplanned", reason="Disk failure", user=self.manager)
        entry = AuditEvent.objects.for_entity("operations.DowntimeEvent", event.pk).first()
        self.assertIn("downtime declared", entry.entity_label)
        self.assertEqual(entry.reason, "Disk failure")

    def test_ending_does_not_close_the_outage(self):
        event = continuity.declare(kind="unplanned", reason="Network", user=self.manager)
        continuity.end(event, user=self.manager, recovery_notes="Switch replaced.")

        self.assertIsNotNone(event.ended_at)
        self.assertFalse(event.is_open)
        self.assertFalse(event.is_reconciled)
        self.assertTrue(event.needs_reconciliation)

    def test_ending_puts_reconciliation_on_the_exception_queue(self):
        event = continuity.declare(kind="unplanned", reason="Network", user=self.manager)
        continuity.end(event, user=self.manager, recovery_notes="Fixed.")

        item = ExceptionItem.objects.get(source_key=f"downtime-reconcile:{event.pk}")
        self.assertTrue(item.is_open)
        self.assertEqual(item.severity, "high")

    def test_reconciling_clears_the_exception(self):
        event = continuity.declare(kind="unplanned", reason="Network", user=self.manager)
        continuity.end(event, user=self.manager, recovery_notes="Fixed.")
        continuity.reconcile(event, user=self.manager, notes="All 12 results entered.")

        self.assertTrue(event.is_reconciled)
        item = ExceptionItem.objects.get(source_key=f"downtime-reconcile:{event.pk}")
        self.assertFalse(item.is_open)

    def test_an_open_outage_cannot_be_reconciled(self):
        event = continuity.declare(kind="unplanned", reason="Network", user=self.manager)
        with self.assertRaises(ControlViolation):
            continuity.reconcile(event, user=self.manager)


class ReadOnlyModeTests(TestCase):
    def setUp(self):
        self.manager = make_user("mgr", role="manager", password=PASSWORD)
        self.scientist = make_user("bms", password=PASSWORD)
        self.patient = make_patient()

    def test_it_is_off_by_default(self):
        self.assertFalse(continuity.is_read_only())

    def test_setting_it_is_audited(self):
        continuity.set_read_only("Restoring from backup", user=self.manager)
        self.assertEqual(continuity.read_only_reason(), "Restoring from backup")

        entry = AuditEvent.objects.for_entity(
            "operations.SystemSetting", continuity.READ_ONLY_KEY
        ).first()
        self.assertIn("read-only", entry.entity_label)

    def test_writes_are_refused_while_read_only(self):
        continuity.set_read_only("Restoring from backup", user=self.manager)
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("patients:patient_create"),
            {"first_name": "New", "last_name": "Patient",
             "dob": "1990-01-01", "gender": "F", "mrn": "MRN-NEW"},
        )
        from apps.patients.models import Patient

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Patient.objects.filter(mrn="MRN-NEW").exists())

    def test_reads_still_work_while_read_only(self):
        continuity.set_read_only("Restoring", user=self.manager)
        self.client.force_login(self.manager)
        response = self.client.get(reverse("patients:patient_list"))
        self.assertEqual(response.status_code, 200)

    def test_signing_out_still_works_while_read_only(self):
        """Trapping people in a session they cannot leave achieves nothing."""
        continuity.set_read_only("Restoring", user=self.manager)
        self.client.force_login(self.manager)
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)

    def test_the_api_gets_a_machine_readable_refusal(self):
        from apps.api.models import ApiClient, Scope

        continuity.set_read_only("Restoring", user=self.manager)
        _client, token = ApiClient.issue(
            name="Ward", scopes=[Scope.PATIENTS_WRITE], purpose="ward",
        )
        response = self.client.post(
            "/api/v1/patients/new/", data="{}", content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "read_only")

    def test_lifting_it_restores_writes(self):
        continuity.set_read_only("Restoring", user=self.manager)
        continuity.set_read_only(None, user=self.manager)
        self.assertFalse(continuity.is_read_only())


class BackloadTests(TestCase):
    def setUp(self):
        self.scientist = make_user("bms", password=PASSWORD)
        self.clerk = make_user("clerk1", role="clerk", password=PASSWORD)
        self.manager = make_user("mgr", role="manager", password=PASSWORD)
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])
        self.event = continuity.declare(
            kind="unplanned", reason="Outage", user=self.manager,
        )
        self.performed = timezone.now() - timedelta(hours=5)

    def _backload(self, **overrides):
        kwargs = {
            "order": self.order,
            "values": {self.test.id: "5.4"},
            "event": self.event,
            "performed_by": "A. Nolan",
            "performed_at": self.performed,
            "keyed_by": self.scientist,
        }
        kwargs.update(overrides)
        return continuity.backload(**kwargs)

    def test_the_result_names_who_performed_it_not_who_typed_it(self):
        self._backload()
        result = Result.objects.get(order=self.order)

        self.assertEqual(result.entered_by, "A. Nolan")
        self.assertNotEqual(result.entered_by, self.scientist.username)

    def test_the_result_carries_the_time_it_was_produced(self):
        self._backload()
        result = Result.objects.get(order=self.order)
        self.assertEqual(result.timestamp, self.performed)

    def test_the_comment_records_both_people(self):
        self._backload()
        result = Result.objects.get(order=self.order)

        self.assertIn("A. Nolan", result.comments)
        self.assertIn(self.scientist.username, result.comments)
        self.assertIn(self.event.reference, result.comments)

    def test_flags_are_computed_as_normal(self):
        self._backload(values={self.test.id: "30.0"})
        result = Result.objects.get(order=self.order)
        self.assertIn("Critical High", result.result_flags)

    def test_a_backloaded_result_is_not_verified(self):
        """It still has to go through validation like anything else."""
        self._backload()
        result = Result.objects.get(order=self.order)

        self.assertEqual(result.status, OrderStatus.RESULTED)
        self.assertIsNone(result.clinical_verified_by)

    def test_the_performer_is_required(self):
        with self.assertRaises(ControlViolation):
            self._backload(performed_by="   ")

    def test_a_future_time_is_refused(self):
        with self.assertRaises(ControlViolation):
            self._backload(performed_at=timezone.now() + timedelta(hours=1))

    def test_the_count_accumulates_on_the_outage(self):
        self._backload()
        second = make_test(code="K", name="Potassium")
        self.order.tests.add(second)
        self._backload(values={second.id: "4.1"})

        self.event.refresh_from_db()
        self.assertEqual(self.event.backloaded_results, 2)

    def test_backloading_is_audited_with_the_attribution(self):
        self._backload()
        entry = AuditEvent.objects.for_entity("laboratory.Order", self.order.pk).first()
        self.assertIn("backloaded from downtime", entry.entity_label)
        self.assertIn("A. Nolan", entry.reason)


class PackTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test], accession="2026-09-16-0001")

    def test_the_pack_lists_outstanding_orders(self):
        document, stats = continuity.build_pack()

        self.assertIn("2026-09-16-0001", document)
        self.assertIn(self.patient.mrn, document)
        self.assertIn("Jane Doe", document)
        self.assertEqual(stats["orders"], 1)

    def test_a_completed_order_is_not_in_the_pack(self):
        self.order.status = OrderStatus.COMPLETED
        self.order.save(update_fields=["status"])
        _document, stats = continuity.build_pack()
        self.assertEqual(stats["orders"], 0)

    def test_the_pack_carries_reference_and_critical_limits(self):
        document, _ = continuity.build_pack()
        self.assertIn("Reference intervals and critical limits", document)
        self.assertIn("GLU", document)
        self.assertIn("25", document)  # the panic high

    def test_the_pack_is_self_contained(self):
        """No server, no database, no network — those are what is missing."""
        document, _ = continuity.build_pack()

        self.assertNotIn("<script", document.lower())
        self.assertNotIn("<link", document.lower())
        self.assertNotIn("http://", document)
        self.assertNotIn("src=", document.lower())

    def test_patient_names_are_escaped(self):
        self.patient.last_name = "O'Brien <script>"
        self.patient.save(update_fields=["last_name"])
        document, _ = continuity.build_pack()

        self.assertIn("&lt;script&gt;", document)
        self.assertNotIn("<script>", document)

    def test_writing_records_the_pack(self):
        with tempfile.TemporaryDirectory() as directory:
            pack = continuity.write_pack(
                directory=Path(directory), generated_by="tester"
            )
            self.assertTrue(Path(pack.path).exists())
            self.assertEqual(pack.order_count, 1)
            self.assertFalse(pack.encrypted)
            self.assertEqual(DowntimePack.objects.count(), 1)

            # A stable filename the procedure can name.
            self.assertTrue((Path(directory) / "downtime-pack-latest.html").exists())

    def test_an_encrypted_pack_is_not_readable_as_text(self):
        with tempfile.TemporaryDirectory() as directory:
            pack = continuity.write_pack(
                directory=Path(directory), passphrase="a-long-enough-passphrase"
            )
            raw = Path(pack.path).read_bytes()

            self.assertTrue(pack.encrypted)
            self.assertNotIn(b"MRN001", raw)

            from apps.compliance.encryption import decrypt_bytes

            recovered = decrypt_bytes(raw, "a-long-enough-passphrase").decode()
            self.assertIn("MRN001", recovered)

    def test_a_stale_pack_is_identifiable(self):
        pack = DowntimePack.objects.create(path="/tmp/x", order_count=0)
        self.assertFalse(pack.is_stale)

        pack.generated_at = timezone.now() - timedelta(hours=20)
        pack.save(update_fields=["generated_at"])
        self.assertTrue(pack.is_stale)


class ScreenTests(TestCase):
    def setUp(self):
        self.manager = make_user("mgr", role="manager", password=PASSWORD)
        self.client.force_login(self.manager)

    def test_the_downtime_screen_renders(self):
        response = self.client.get(reverse("operations:downtime_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Downtime record")

    def test_declaring_through_the_screen_works(self):
        self.client.post(reverse("operations:downtime_declare"), {
            "kind": "unplanned",
            "began_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "reason": "Storage array failure",
            "impact": "All disciplines",
        })
        self.assertEqual(DowntimeEvent.objects.count(), 1)

    def test_declaring_can_also_make_the_system_read_only(self):
        self.client.post(reverse("operations:downtime_declare"), {
            "kind": "planned",
            "began_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "reason": "Restoring from backup",
            "read_only": "on",
        })
        self.assertTrue(continuity.is_read_only())

    def test_a_scientist_cannot_declare_downtime(self):
        scientist = make_user("bms", password=PASSWORD)
        self.client.force_login(scientist)
        response = self.client.get(reverse("operations:downtime_list"))
        self.assertEqual(response.status_code, 403)

    def test_the_installer_can_declare_downtime(self):
        """Outages are noticed at 3am by whoever maintains the server."""
        installer = make_user("inst", role="installer", password=PASSWORD)
        self.client.force_login(installer)
        response = self.client.get(reverse("operations:downtime_list"))
        self.assertEqual(response.status_code, 200)

    def test_the_backload_screen_parses_code_equals_value(self):
        patient = make_patient()
        test = make_test()
        order = make_order(patient, [test], accession="2026-09-16-0007")
        event = continuity.declare(kind="unplanned", reason="Outage", user=self.manager)

        self.client.post(reverse("operations:downtime_backload", args=[event.pk]), {
            "accession_number": "2026-09-16-0007",
            "performed_by": "A. Nolan",
            "performed_at": (timezone.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
            "values": "GLU = 5.4",
        })
        self.assertTrue(Result.objects.filter(order=order, value="5.4").exists())

    def test_an_unknown_test_code_is_reported_rather_than_dropped(self):
        patient = make_patient()
        test = make_test()
        order = make_order(patient, [test], accession="2026-09-16-0008")
        event = continuity.declare(kind="unplanned", reason="Outage", user=self.manager)

        self.client.post(reverse("operations:downtime_backload", args=[event.pk]), {
            "accession_number": "2026-09-16-0008",
            "performed_by": "A. Nolan",
            "performed_at": (timezone.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
            "values": "GLU = 5.4\nNOPE = 1.0",
        })
        self.assertEqual(Result.objects.filter(order=order).count(), 0)
