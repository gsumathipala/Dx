"""The unified exception queue: raising, deduplicating, sweeping and closing."""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clinical.models import CriticalValueNotification
from apps.compliance.services import ControlViolation
from apps.interop.models import InstrumentInterface, InstrumentMessage
from apps.operations.exceptions import (
    ExceptionSource, acknowledge, auto_resolve, raise_exception, resolve, sweep,
)
from apps.operations.models import ExceptionItem, TatBreach
from apps.quality.models import QcRun
from tests.factories import make_order, make_patient, make_test, make_user, passing_qc


class RaisingTests(TestCase):
    def test_raising_creates_an_item(self):
        item = raise_exception(
            source=ExceptionSource.MANUAL, source_key="k1", title="Something",
        )
        self.assertTrue(item.is_open)
        self.assertEqual(item.occurrences, 1)

    def test_the_same_problem_twice_bumps_rather_than_duplicates(self):
        raise_exception(source=ExceptionSource.MANUAL, source_key="k1", title="Something")
        raise_exception(source=ExceptionSource.MANUAL, source_key="k1", title="Something")

        self.assertEqual(ExceptionItem.objects.count(), 1)
        self.assertEqual(ExceptionItem.objects.get().occurrences, 2)

    def test_a_resolved_problem_that_returns_is_reopened(self):
        user = make_user("bms")
        item = raise_exception(
            source=ExceptionSource.MANUAL, source_key="k1", title="Flaky analyser"
        )
        resolve(item, user, resolution="Reseated the probe.")

        raise_exception(
            source=ExceptionSource.MANUAL, source_key="k1", title="Flaky analyser"
        )
        item.refresh_from_db()

        self.assertTrue(item.is_open)
        self.assertEqual(item.occurrences, 2)
        self.assertEqual(item.resolution, "")

    def test_an_item_inherits_the_patient_from_its_order(self):
        patient = make_patient()
        order = make_order(patient, [])
        item = raise_exception(
            source=ExceptionSource.TAT_BREACH, source_key="k2", title="Late", order=order
        )
        self.assertEqual(item.patient_id, patient.pk)


class ClosingTests(TestCase):
    def setUp(self):
        self.user = make_user("bms")
        self.item = raise_exception(
            source=ExceptionSource.MANUAL, source_key="k1", title="Something",
        )

    def test_closing_needs_a_reason(self):
        with self.assertRaises(ControlViolation):
            resolve(self.item, self.user, resolution="  ")

    def test_acknowledging_assigns_it(self):
        acknowledge(self.item, self.user)
        self.assertEqual(self.item.status, ExceptionItem.Status.ACKNOWLEDGED)
        self.assertEqual(self.item.assigned_to, self.user)

    def test_resolving_can_open_a_corrective_action(self):
        resolve(
            self.item, self.user, resolution="Root cause found.", raise_capa=True
        )
        self.assertIsNotNone(self.item.corrective_action)

    def test_dismissing_is_distinguishable_from_resolving(self):
        resolve(self.item, self.user, resolution="Not a real problem.", dismissed=True)
        self.assertEqual(self.item.status, ExceptionItem.Status.DISMISSED)

    def test_auto_resolve_closes_without_a_user(self):
        auto_resolve("k1", "The condition cleared.")
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExceptionItem.Status.RESOLVED)
        self.assertIsNone(self.item.resolved_by)


class SweepTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])

    def test_an_overdue_critical_value_is_swept_up(self):
        CriticalValueNotification.objects.create(
            order=self.order, test=self.test, patient=self.patient,
            test_code=self.test.code, value="30", threshold="> 25",
            critical_type=CriticalValueNotification.CriticalType.HIGH,
            created_by="tech",
            escalation_due_at=timezone.now() - timedelta(minutes=5),
        )
        sweep()
        self.assertTrue(
            ExceptionItem.objects.filter(source=ExceptionSource.CRITICAL_VALUE).exists()
        )

    def test_an_acknowledged_critical_value_closes_itself(self):
        notification = CriticalValueNotification.objects.create(
            order=self.order, test=self.test, patient=self.patient,
            test_code=self.test.code, value="30", threshold="> 25",
            critical_type=CriticalValueNotification.CriticalType.HIGH,
            created_by="tech",
            escalation_due_at=timezone.now() - timedelta(minutes=5),
        )
        sweep()
        notification.status = CriticalValueNotification.Status.ACKNOWLEDGED
        notification.save(update_fields=["status"])
        sweep()

        item = ExceptionItem.objects.get(source=ExceptionSource.CRITICAL_VALUE)
        self.assertFalse(item.is_open)

    def test_a_silent_interface_is_swept_up_and_clears_when_it_talks(self):
        interface = InstrumentInterface.objects.create(
            name="ARCH-1", enabled=True,
            last_message_at=timezone.now() - timedelta(hours=3),
        )
        sweep()
        item = ExceptionItem.objects.get(source=ExceptionSource.INTERFACE_STALE)
        self.assertTrue(item.is_open)

        interface.last_message_at = timezone.now()
        interface.save(update_fields=["last_message_at"])
        sweep()

        item.refresh_from_db()
        self.assertFalse(item.is_open)

    def test_a_failed_instrument_message_is_swept_up(self):
        InstrumentMessage.objects.create(
            raw_payload="junk", status=InstrumentMessage.Status.FAILED,
            error="No accession number",
        )
        sweep()
        self.assertTrue(
            ExceptionItem.objects.filter(source=ExceptionSource.INSTRUMENT).exists()
        )

    def test_a_failed_qc_run_is_swept_up(self):
        run = passing_qc(self.test)
        run.status = QcRun.Status.FAIL
        run.result_flags = ["1-3s"]
        run.save(update_fields=["status", "result_flags"])

        sweep()
        item = ExceptionItem.objects.get(source=ExceptionSource.QC_FAILURE)
        self.assertEqual(item.severity, ExceptionItem.Severity.CRITICAL)

    def test_a_breached_turnaround_is_swept_up(self):
        TatBreach.objects.create(
            order=self.order, actual_hours=8.0, target_hours=4.0,
            breach_type=TatBreach.BreachType.CRITICAL,
        )
        sweep()
        self.assertTrue(
            ExceptionItem.objects.filter(source=ExceptionSource.TAT_BREACH).exists()
        )

    def test_sweeping_twice_does_not_duplicate(self):
        InstrumentMessage.objects.create(
            raw_payload="junk", status=InstrumentMessage.Status.FAILED, error="bad",
        )
        sweep()
        sweep()
        self.assertEqual(
            ExceptionItem.objects.filter(source=ExceptionSource.INSTRUMENT).count(), 1
        )

    def test_one_failing_sweep_does_not_stop_the_others(self):
        """A broken sweep must not silence every other sweep behind it."""
        from unittest.mock import patch

        from apps.operations import exceptions as module

        InstrumentMessage.objects.create(
            raw_payload="junk", status=InstrumentMessage.Status.FAILED, error="bad",
        )

        def explode():
            raise RuntimeError("boom")

        broken = (("critical values", explode),) + tuple(
            entry for entry in module.SWEEPS if entry[0] != "critical values"
        )
        with patch.object(module, "SWEEPS", broken):
            counts = sweep()

        self.assertEqual(counts["critical values"], -1)
        self.assertTrue(
            ExceptionItem.objects.filter(source=ExceptionSource.INSTRUMENT).exists()
        )


class QueueScreenTests(TestCase):
    def setUp(self):
        self.user = make_user("bms", password="Str0ng-Pass!23")
        self.item = raise_exception(
            source=ExceptionSource.MANUAL, source_key="k1", title="Check the fridge",
            severity=ExceptionItem.Severity.HIGH,
        )
        self.client.force_login(self.user)

    def test_the_queue_lists_open_items(self):
        response = self.client.get(reverse("operations:exception_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check the fridge")

    def test_a_resolved_item_is_hidden_by_default(self):
        resolve(self.item, self.user, resolution="Done.")
        response = self.client.get(reverse("operations:exception_list"))
        self.assertNotContains(response, "Check the fridge")

    def test_closing_through_the_screen_requires_a_note(self):
        response = self.client.post(
            reverse("operations:exception_resolve", args=[self.item.pk]),
            {"resolution": ""},
        )
        self.item.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.item.is_open)

    def test_closing_through_the_screen_works(self):
        self.client.post(
            reverse("operations:exception_resolve", args=[self.item.pk]),
            {"resolution": "Compressor restarted."},
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ExceptionItem.Status.RESOLVED)

    def test_severity_orders_the_queue_not_the_alphabet(self):
        raise_exception(
            source=ExceptionSource.MANUAL, source_key="k2", title="Low priority",
            severity=ExceptionItem.Severity.LOW,
        )
        raise_exception(
            source=ExceptionSource.MANUAL, source_key="k3", title="Urgent thing",
            severity=ExceptionItem.Severity.CRITICAL,
        )
        response = self.client.get(reverse("operations:exception_list"))
        body = response.content.decode()
        self.assertLess(body.index("Urgent thing"), body.index("Check the fridge"))
        self.assertLess(body.index("Check the fridge"), body.index("Low priority"))


class InstallerRedactionTests(TestCase):
    """The installer may see that something is wrong, never what it is about."""

    def test_the_installer_cannot_reach_the_exception_queue(self):
        installer = make_user("inst", role="installer", password="Str0ng-Pass!23")
        self.client.force_login(installer)
        response = self.client.get(reverse("operations:exception_list"))
        self.assertEqual(response.status_code, 403)


class DetailScreenTests(TestCase):
    def setUp(self):
        self.user = make_user("bms", password="Str0ng-Pass!23")
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])
        self.item = raise_exception(
            source=ExceptionSource.QC_FAILURE, source_key="k9",
            title="QC failed for GLU", detail="Control gave 9.9 — 1-3s.",
            severity=ExceptionItem.Severity.CRITICAL, order=self.order,
            test_code="GLU",
        )
        self.client.force_login(self.user)

    def test_the_detail_screen_renders(self):
        response = self.client.get(
            reverse("operations:exception_detail", args=[self.item.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "QC failed for GLU")
        self.assertContains(response, self.order.accession_number)

    def test_acknowledging_through_the_screen_assigns_it(self):
        self.client.post(
            reverse("operations:exception_acknowledge", args=[self.item.pk])
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.assigned_to, self.user)

    def test_a_closed_item_offers_no_actions(self):
        resolve(self.item, self.user, resolution="Repeated QC.")
        response = self.client.get(
            reverse("operations:exception_detail", args=[self.item.pk])
        )
        self.assertNotContains(response, "Acknowledge and take it")
