"""Accessioning, result entry and the regulatory gates around validation."""
from __future__ import annotations

import threading
from datetime import timedelta

from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.common.constants import AuditAction, OrderStatus
from apps.compliance.models import ElectronicSignature
from apps.compliance.services import ControlViolation
from apps.inventory.models import InventoryItem, InventoryTransaction
from apps.inventory.services import consume_reagent
from apps.laboratory.models import Order, Result
from apps.laboratory.services import create_order, generate_accession_number, save_results
from tests.factories import (
    failing_qc, grant_competency, make_patient, make_test, make_user, passing_qc,
)


class AccessionNumberTests(TestCase):
    def test_sequence_starts_at_one_and_increments(self):
        patient = make_patient()
        test = make_test()
        first = create_order(patient=patient, tests=[test], ordered_by="Dr A")
        second = create_order(patient=patient, tests=[test], ordered_by="Dr A")
        today = timezone.localdate().strftime("%Y-%m-%d")
        self.assertEqual(first.accession_number, f"{today}-0001")
        self.assertEqual(second.accession_number, f"{today}-0002")

    def test_suffix_is_parsed_numerically_not_lexically(self):
        """Past 9999 a text comparison would wrap and reissue a used number."""
        today = timezone.localdate().strftime("%Y-%m-%d")
        patient = make_patient()
        Order.objects.create(
            patient=patient, accession_number=f"{today}-9999",
            status=OrderStatus.PENDING, timestamp=timezone.now(),
        )
        self.assertEqual(generate_accession_number(), f"{today}-10000")


class ConcurrentAccessionTests(TransactionTestCase):
    """The original reserved the number outside the inserting transaction, so
    concurrent accessioning could hand out duplicates."""

    reset_sequences = True

    def test_concurrent_orders_get_distinct_numbers(self):
        patient = make_patient()
        test = make_test()
        errors: list[Exception] = []
        created: list[str] = []
        lock = threading.Lock()

        def worker():
            try:
                order = create_order(patient=patient, tests=[test], ordered_by="Dr A")
                with lock:
                    created.append(order.accession_number)
            except Exception as exc:  # pragma: no cover - surfaced by assertion
                with lock:
                    errors.append(exc)
            finally:
                # Close only this thread's connection; close_all() would tear
                # down the connections the other workers are still using.
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [], f"accessioning raised: {errors}")
        self.assertEqual(len(created), 8)
        self.assertEqual(len(set(created)), 8, f"duplicate accession numbers: {created}")


class ResultEntryTests(TestCase):
    def setUp(self):
        self.password = "Str0ng-Pass!23"
        self.tech = make_user("tech", password=self.password)
        self.senior = make_user("senior", role="manager", password=self.password)
        self.test = make_test()
        self.patient = make_patient()
        self.order = create_order(patient=self.patient, tests=[self.test], ordered_by="Dr A")
        grant_competency(self.tech, test=self.test)
        grant_competency(self.senior, test=self.test)
        passing_qc(self.test)

    def test_entry_creates_result_and_sets_flags(self):
        outcome = save_results(
            order=self.order, values={self.test.id: "9.9"}, user=self.tech
        )
        result = outcome["results"][0]
        self.assertEqual(result.numeric_value, 9.9)
        self.assertEqual(result.result_flags, ["High"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.RESULTED)

    def test_entry_is_idempotent_per_test(self):
        save_results(order=self.order, values={self.test.id: "5.0"}, user=self.tech)
        save_results(order=self.order, values={self.test.id: "6.0"}, user=self.tech)
        self.assertEqual(Result.objects.filter(order=self.order, test_key=self.test.id).count(), 1)
        self.assertEqual(Result.objects.get(order=self.order, test_key=self.test.id).value, "6.0")

    def test_notes_are_stored_on_the_report_pseudo_row(self):
        save_results(order=self.order, values={self.test.id: "5.0"},
                     user=self.tech, notes="Sample slightly haemolysed")
        report = Result.objects.get(order=self.order, test_key=Result.REPORT_TEST_ID)
        self.assertEqual(report.comments, "Sample slightly haemolysed")

    def test_clinical_verification_completes_the_order_and_signs_it(self):
        save_results(order=self.order, values={self.test.id: "5.0"}, user=self.tech)
        outcome = save_results(
            order=self.order, values={self.test.id: "5.0"}, user=self.senior,
            action=AuditAction.CLINICAL_VERIFY, password=self.password,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertIsNotNone(self.order.completed_at)
        self.assertIsNotNone(outcome["signature"])
        self.assertEqual(
            outcome["signature"].meaning, ElectronicSignature.Meaning.CLINICAL_APPROVAL
        )

    def test_verification_blocked_without_signature_password(self):
        save_results(order=self.order, values={self.test.id: "5.0"}, user=self.tech)
        with self.assertRaises(ControlViolation):
            save_results(order=self.order, values={self.test.id: "5.0"}, user=self.senior,
                         action=AuditAction.CLINICAL_VERIFY)

    def test_verification_blocked_for_the_entering_analyst(self):
        save_results(order=self.order, values={self.test.id: "5.0"}, user=self.tech)
        with self.assertRaises(ControlViolation) as ctx:
            save_results(order=self.order, values={self.test.id: "5.0"}, user=self.tech,
                         action=AuditAction.CLINICAL_VERIFY, password=self.password)
        self.assertIn("cannot also verify", str(ctx.exception))

    def test_verification_blocked_without_competency(self):
        stranger = make_user("stranger", role="manager", password=self.password)
        save_results(order=self.order, values={self.test.id: "5.0"}, user=self.tech)
        with self.assertRaises(ControlViolation) as ctx:
            save_results(order=self.order, values={self.test.id: "5.0"}, user=stranger,
                         action=AuditAction.CLINICAL_VERIFY, password=self.password)
        self.assertIn("competency", str(ctx.exception).lower())

    def test_verification_blocked_when_qc_failed(self):
        other_test = make_test(code="NA", name="Sodium")
        grant_competency(self.senior, test=other_test)
        failing_qc(other_test)
        order = create_order(patient=self.patient, tests=[other_test], ordered_by="Dr A")
        save_results(order=order, values={other_test.id: "140"}, user=self.tech)
        with self.assertRaises(ControlViolation) as ctx:
            save_results(order=order, values={other_test.id: "140"}, user=self.senior,
                         action=AuditAction.CLINICAL_VERIFY, password=self.password)
        self.assertIn("QC", str(ctx.exception))

    def test_nothing_is_written_when_a_gate_blocks(self):
        """The gates run before any write, and the transaction rolls back."""
        other = make_test(code="K", name="Potassium")
        failing_qc(other)
        grant_competency(self.senior, test=other)
        order = create_order(patient=self.patient, tests=[other], ordered_by="Dr A")
        with self.assertRaises(ControlViolation):
            save_results(order=order, values={other.id: "4.0"}, user=self.senior,
                         action=AuditAction.CLINICAL_VERIFY, password=self.password)
        self.assertFalse(Result.objects.filter(order=order).exists())
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PENDING)

    def test_unknown_test_is_rejected(self):
        from apps.laboratory.services import ResultEntryError

        with self.assertRaises(ResultEntryError):
            save_results(order=self.order, values={"no-such-test": "1"}, user=self.tech)


class ReagentConsumptionTests(TestCase):
    def setUp(self):
        self.test = make_test()
        self.item = InventoryItem.objects.create(
            name="Glucose reagent", quantity=5, unit="tests",
            expiration_date=timezone.localdate() + timedelta(days=90),
        )
        self.item.tests.add(self.test)

    def test_consumption_decrements_and_logs(self):
        transaction_row = consume_reagent(self.test, "tech")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 4)
        self.assertEqual(transaction_row.change, -1)
        self.assertEqual(transaction_row.balance_after, 4)

    def test_unlinked_test_consumes_nothing(self):
        """The original matched reagents by substring on the test code, which
        consumed the wrong item when one code prefixed another."""
        other = make_test(code="GLUC2", name="Glucose fasting")
        self.assertIsNone(consume_reagent(other, "tech"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 5)

    def test_expired_reagent_is_not_consumed(self):
        self.item.expiration_date = timezone.localdate() - timedelta(days=1)
        self.item.save()
        self.assertIsNone(consume_reagent(self.test, "tech"))

    def test_stock_never_goes_negative(self):
        self.item.quantity = 1
        self.item.save()
        self.assertIsNotNone(consume_reagent(self.test, "tech"))
        self.assertIsNone(consume_reagent(self.test, "tech"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 0)
