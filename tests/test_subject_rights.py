"""GDPR data subject rights.

The erasure tests carry the weight. A system that deletes on request destroys
records the laboratory is required by law to keep, and does so irreversibly;
the correct behaviour is a documented, specific refusal for anything inside its
retention period and erasure of everything past it.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.common.constants import OrderStatus
from apps.compliance import subject_rights
from apps.compliance.encryption import decrypt_bytes
from apps.compliance.models import (
    DataSubjectRequest, ProcessingRestriction, RetentionSchedule,
)
from apps.compliance.services import ControlViolation
from apps.laboratory.models import Result
from tests.factories import make_order, make_patient, make_test, make_user


class ReceiptTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.user = make_user("mgr", role="manager")

    def test_references_are_sequential_within_the_year(self):
        first = subject_rights.receive(
            patient=self.patient, kind=DataSubjectRequest.Kind.ACCESS,
            requested_by="Jane Doe",
        )
        second = subject_rights.receive(
            patient=self.patient, kind=DataSubjectRequest.Kind.ERASURE,
            requested_by="Jane Doe",
        )
        year = timezone.now().year
        self.assertEqual(first.reference, f"DSR-{year}-0001")
        self.assertEqual(second.reference, f"DSR-{year}-0002")

    def test_the_clock_starts_on_receipt_not_on_verification(self):
        request = subject_rights.receive(
            patient=self.patient, kind=DataSubjectRequest.Kind.ACCESS,
            requested_by="Jane Doe",
        )
        self.assertFalse(request.identity_verified)
        self.assertAlmostEqual(
            (request.due_at - request.received_at).days,
            DataSubjectRequest.RESPONSE_DAYS,
            delta=1,
        )

    def test_a_new_request_awaits_identity_verification(self):
        request = subject_rights.receive(
            patient=self.patient, kind=DataSubjectRequest.Kind.ACCESS,
            requested_by="Jane Doe",
        )
        self.assertEqual(request.status, DataSubjectRequest.Status.IDENTITY_PENDING)
        self.assertFalse(request.is_actionable)

    def test_identity_verification_needs_evidence(self):
        request = subject_rights.receive(
            patient=self.patient, kind=DataSubjectRequest.Kind.ACCESS,
            requested_by="Jane Doe",
        )
        with self.assertRaises(ControlViolation):
            subject_rights.verify_identity(request, user=self.user, evidence="  ")

    def test_the_extension_can_only_be_taken_once(self):
        request = subject_rights.receive(
            patient=self.patient, kind=DataSubjectRequest.Kind.ACCESS,
            requested_by="Jane Doe",
        )
        original = request.due_at
        subject_rights.extend(request, reason="The record spans twelve years.")
        self.assertEqual(
            (request.due_at - original).days, DataSubjectRequest.EXTENSION_DAYS
        )
        with self.assertRaises(ControlViolation):
            subject_rights.extend(request, reason="Again.")


class ExportTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])
        Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id, value="5.0",
            status=OrderStatus.COMPLETED, entered_by="tech",
            clinical_verified_by="rule:Release routine chemistry",
        )

    def test_the_access_export_covers_what_article_15_requires(self):
        document = subject_rights.build_export(self.patient)

        self.assertEqual(document["subject"]["mrn"], self.patient.mrn)
        self.assertIn("purposes_of_processing", document)
        self.assertIn("retention", document)
        self.assertIn("disclosures", document)
        self.assertEqual(len(document["orders"]), 1)

    def test_automated_decision_making_is_declared(self):
        """Article 15(1)(h) requires it, and autoverification is exactly that."""
        document = subject_rights.build_export(self.patient)
        block = document["automated_decision_making"]
        self.assertTrue(block["in_use"])
        self.assertEqual(block["results_released_automatically"], 1)

    def test_the_portability_export_is_a_fhir_bundle(self):
        document = subject_rights.build_export(self.patient, portable=True)
        self.assertEqual(document["resourceType"], "Bundle")
        types = {entry["resource"]["resourceType"] for entry in document["entry"]}
        self.assertIn("Patient", types)
        self.assertIn("DiagnosticReport", types)

    def test_the_export_is_written_encrypted(self):
        import tempfile

        request = subject_rights.receive(
            patient=self.patient, kind=DataSubjectRequest.Kind.ACCESS,
            requested_by="Jane Doe",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = subject_rights.write_export(
                request, passphrase="a-long-enough-passphrase", directory=Path(directory)
            )
            raw = path.read_bytes()

            # Not readable without the passphrase.
            self.assertNotIn(b"MRN001", raw)
            recovered = json.loads(
                decrypt_bytes(raw, "a-long-enough-passphrase").decode("utf-8")
            )
            self.assertEqual(recovered["subject"]["mrn"], "MRN001")


class ErasureTests(TestCase):
    def setUp(self):
        self.user = make_user("mgr", role="manager")
        self.patient = make_patient()
        self.test = make_test()
        # The schedule is seeded by a data migration; pin the period this
        # test reasons about rather than depending on the seeded value.
        RetentionSchedule.objects.update_or_create(
            record_class=RetentionSchedule.RecordClass.TEST_RECORD,
            defaults={"retention_years": 2, "citation": "CLIA 42 CFR §493.1105",
                      "active": True},
        )
        RetentionSchedule.objects.exclude(
            record_class=RetentionSchedule.RecordClass.TEST_RECORD
        ).update(active=False)

    def _order(self, *, years_ago: int):
        when = timezone.now() - timedelta(days=365 * years_ago)
        order = make_order(
            self.patient, [self.test], when=when,
            accession=f"{when:%Y-%m-%d}-{years_ago:04d}",
        )
        order.completed_at = when
        order.status = OrderStatus.COMPLETED
        order.save(update_fields=["completed_at", "status"])
        Result.objects.create(
            order=order, test=self.test, test_key=self.test.id, value="5.0",
            entered_by="tech",
        )
        return order

    def _request(self, verified=True):
        request = subject_rights.receive(
            patient=self.patient, kind=DataSubjectRequest.Kind.ERASURE,
            requested_by="Jane Doe",
        )
        if verified:
            subject_rights.verify_identity(
                request, user=self.user, evidence="Passport seen in person."
            )
        return request

    def test_a_recent_record_is_refused_with_a_stated_basis(self):
        self._order(years_ago=1)
        assessment = subject_rights.assess_erasure(self.patient)

        self.assertTrue(assessment.wholly_refused)
        self.assertTrue(any("17(3)(b)" in reason for reason in assessment.reasons))
        self.assertTrue(any("retained until" in reason for reason in assessment.reasons))

    def test_a_record_past_its_retention_period_is_erasable(self):
        self._order(years_ago=5)
        assessment = subject_rights.assess_erasure(self.patient)
        self.assertTrue(assessment.fully_erasable)

    def test_performing_erasure_refuses_what_it_must_and_erases_what_it_can(self):
        recent = self._order(years_ago=1)
        old = self._order(years_ago=5)

        request = self._request()
        subject_rights.perform_erasure(request, user=self.user)

        request.refresh_from_db()
        self.assertEqual(request.status, DataSubjectRequest.Status.PARTIALLY_REFUSED)
        self.assertIn("17(3)(b)", request.refusal_basis)

        self.assertIsNone(Result.objects.get(order=old).value)
        self.assertEqual(Result.objects.get(order=recent).value, "5.0")

    def test_erasure_keeps_the_record_shell_so_the_audit_trail_still_resolves(self):
        old = self._order(years_ago=5)
        subject_rights.perform_erasure(self._request(), user=self.user)

        old.refresh_from_db()
        self.assertEqual(old.accession_number[:4], f"{old.timestamp:%Y}")
        self.assertTrue(Result.objects.filter(order=old).exists())

    def test_identifiers_go_only_when_nothing_clinical_is_retained(self):
        self._order(years_ago=5)
        subject_rights.perform_erasure(self._request(), user=self.user)

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.last_name, "[erased]")

    def test_identifiers_are_kept_while_any_record_is_retained(self):
        self._order(years_ago=1)
        subject_rights.perform_erasure(self._request(), user=self.user)

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.last_name, "Doe")

    def test_erasure_without_verified_identity_is_refused(self):
        self._order(years_ago=5)
        with self.assertRaises(ControlViolation):
            subject_rights.perform_erasure(self._request(verified=False), user=self.user)

    def test_a_subject_with_no_records_is_told_so(self):
        assessment = subject_rights.assess_erasure(self.patient)
        self.assertTrue(any("No laboratory records" in r for r in assessment.reasons))


class RestrictionTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.user = make_user("mgr", role="manager")

    def test_a_restriction_is_recorded_and_detectable(self):
        subject_rights.restrict(
            self.patient, reason="Accuracy contested.", user=self.user
        )
        self.assertTrue(subject_rights.is_restricted(self.patient.pk))

    def test_clinical_care_continues_under_a_restriction(self):
        """Article 18(2). Blocking care would endanger the subject it protects."""
        restriction = subject_rights.restrict(
            self.patient, reason="Accuracy contested.", user=self.user
        )
        self.assertTrue(restriction.permits_clinical_care)

    def test_lifting_a_restriction_clears_it(self):
        restriction = subject_rights.restrict(
            self.patient, reason="Contested.", user=self.user
        )
        subject_rights.lift(restriction, reason="Resolved.", user=self.user)
        self.assertFalse(subject_rights.is_restricted(self.patient.pk))

    def test_re_restricting_reuses_the_record(self):
        restriction = subject_rights.restrict(self.patient, reason="A", user=self.user)
        subject_rights.lift(restriction, reason="Done.", user=self.user)
        subject_rights.restrict(self.patient, reason="B", user=self.user)

        self.assertEqual(ProcessingRestriction.objects.count(), 1)
        self.assertTrue(subject_rights.is_restricted(self.patient.pk))


class ScreenTests(TestCase):
    def setUp(self):
        self.manager = make_user("mgr", role="manager", password="Str0ng-Pass!23")
        self.patient = make_patient()
        self.client.force_login(self.manager)

    def test_a_request_can_be_logged_from_the_screen(self):
        self.client.post(reverse("compliance:subject_request_create"), {
            "mrn": self.patient.mrn,
            "kind": DataSubjectRequest.Kind.ACCESS,
            "requested_by": "Jane Doe",
            "relationship": "self",
            "detail": "Everything you hold.",
        })
        self.assertEqual(DataSubjectRequest.objects.count(), 1)

    def test_an_unknown_mrn_does_not_create_a_request(self):
        self.client.post(reverse("compliance:subject_request_create"), {
            "mrn": "NOPE", "kind": DataSubjectRequest.Kind.ACCESS,
            "requested_by": "Jane Doe",
        })
        self.assertEqual(DataSubjectRequest.objects.count(), 0)

    def test_the_installer_cannot_reach_subject_requests(self):
        installer = make_user("inst", role="installer", password="Str0ng-Pass!23")
        self.client.force_login(installer)
        response = self.client.get(reverse("compliance:subject_request_list"))
        self.assertEqual(response.status_code, 403)

    def test_an_overdue_request_is_swept_onto_the_exception_queue(self):
        from apps.operations.exceptions import sweep
        from apps.operations.models import ExceptionItem

        request = subject_rights.receive(
            patient=self.patient, kind=DataSubjectRequest.Kind.ACCESS,
            requested_by="Jane Doe",
        )
        request.due_at = timezone.now() - timedelta(days=1)
        request.save(update_fields=["due_at"])

        sweep()
        self.assertTrue(
            ExceptionItem.objects.filter(source="subject_request").exists()
        )


class DetailScreenTests(TestCase):
    """The detail screen takes an argument, so the smoke test skips it."""

    def setUp(self):
        self.manager = make_user("mgr", role="manager", password="Str0ng-Pass!23")
        self.patient = make_patient()
        self.client.force_login(self.manager)

    def _open(self, kind):
        from django.urls import reverse

        record = subject_rights.receive(
            patient=self.patient, kind=kind, requested_by="Jane Doe",
        )
        return record, self.client.get(
            reverse("compliance:subject_request_detail", args=[record.pk])
        )

    def test_an_access_request_renders(self):
        record, response = self._open(DataSubjectRequest.Kind.ACCESS)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, record.reference)
        self.assertContains(response, "Identity not verified")

    def test_an_erasure_request_shows_the_assessment(self):
        _record, response = self._open(DataSubjectRequest.Kind.ERASURE)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Erasure assessment")

    def test_the_export_form_appears_once_identity_is_verified(self):
        from django.urls import reverse

        record, _ = self._open(DataSubjectRequest.Kind.ACCESS)
        subject_rights.verify_identity(
            record, user=self.manager, evidence="Passport seen."
        )
        response = self.client.get(
            reverse("compliance:subject_request_detail", args=[record.pk])
        )
        self.assertContains(response, "Produce the export")

    def test_exporting_without_verified_identity_is_refused(self):
        from django.urls import reverse

        record, _ = self._open(DataSubjectRequest.Kind.ACCESS)
        self.client.post(
            reverse("compliance:subject_request_export", args=[record.pk]),
            {"passphrase": "a-long-enough-passphrase",
             "confirm": "a-long-enough-passphrase"},
        )
        record.refresh_from_db()
        self.assertEqual(record.export_path, "")

    def test_a_short_passphrase_is_refused(self):
        from django.urls import reverse

        record, _ = self._open(DataSubjectRequest.Kind.ACCESS)
        subject_rights.verify_identity(
            record, user=self.manager, evidence="Passport seen."
        )
        self.client.post(
            reverse("compliance:subject_request_export", args=[record.pk]),
            {"passphrase": "short", "confirm": "short"},
        )
        record.refresh_from_db()
        self.assertEqual(record.export_path, "")
