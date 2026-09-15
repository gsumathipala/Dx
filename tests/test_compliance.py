"""Regulatory controls: competency, QC lockout, self-verification, signatures."""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.recorder import recorder
from apps.compliance.models import AccountSecurityState, ElectronicSignature
from apps.compliance.services import (
    ControlViolation,
    apply_signature,
    check_account_available,
    check_competency,
    check_password_reuse,
    check_qc_status,
    check_self_verification,
    raise_capa,
    record_password_change,
    register_failed_login,
)
from apps.laboratory.models import Result
from tests.factories import (
    failing_qc, grant_competency, make_department, make_order, make_patient,
    make_test, make_user, passing_qc,
)


class CompetencyGatingTests(TestCase):
    def setUp(self):
        self.dept = make_department()
        self.test = make_test(department=self.dept)
        self.user = make_user("tech1")

    def test_blocked_without_competency(self):
        check = check_competency(self.user, self.test)
        self.assertFalse(check.allowed)
        self.assertIn("493.1451", check.citation)
        with self.assertRaises(ControlViolation):
            check.enforce()

    def test_allowed_with_test_specific_competency(self):
        grant_competency(self.user, test=self.test)
        self.assertTrue(check_competency(self.user, self.test).allowed)

    def test_allowed_with_department_wide_competency(self):
        grant_competency(self.user, category=str(self.dept))
        self.assertTrue(check_competency(self.user, self.test).allowed)

    def test_expired_competency_does_not_satisfy_the_gate(self):
        record = grant_competency(self.user, test=self.test)
        record.expiry_date = timezone.localdate() - timedelta(days=1)
        record.save()
        self.assertFalse(check_competency(self.user, self.test).allowed)

    def test_admin_bypasses_gate(self):
        admin = make_user("admin1", role="admin")
        self.assertTrue(check_competency(admin, self.test).allowed)

    @override_settings(ENFORCE_COMPETENCY_GATING=False)
    def test_gate_can_be_disabled_by_configuration(self):
        self.assertTrue(check_competency(self.user, self.test).allowed)


class QcLockoutTests(TestCase):
    def setUp(self):
        self.test = make_test()

    def test_blocked_when_no_qc_in_window(self):
        check = check_qc_status(self.test)
        self.assertFalse(check.allowed)
        self.assertIn("No quality control", check.message)

    def test_blocked_when_latest_qc_failed(self):
        failing_qc(self.test)
        check = check_qc_status(self.test)
        self.assertFalse(check.allowed)
        self.assertIn("failed", check.message)

    def test_allowed_when_qc_passed(self):
        passing_qc(self.test)
        self.assertTrue(check_qc_status(self.test).allowed)

    def test_stale_qc_does_not_satisfy_the_gate(self):
        passing_qc(self.test, when=timezone.now() - timedelta(hours=36))
        self.assertFalse(check_qc_status(self.test).allowed)

    @override_settings(ENFORCE_QC_LOCKOUT=False)
    def test_lockout_can_be_disabled(self):
        self.assertTrue(check_qc_status(self.test).allowed)


class SelfVerificationTests(TestCase):
    def setUp(self):
        self.user = make_user("tech2")
        self.test = make_test()
        patient = make_patient()
        order = make_order(patient, [self.test])
        self.result = Result.objects.create(
            order=order, test=self.test, test_key=self.test.id,
            value="5.0", entered_by=self.user.username,
        )

    def test_entering_analyst_cannot_verify_own_result(self):
        check = check_self_verification(self.user, self.result)
        self.assertFalse(check.allowed)
        self.assertIn("cannot also verify", check.message)

    def test_second_person_may_verify(self):
        other = make_user("tech3")
        self.assertTrue(check_self_verification(other, self.result).allowed)


class ElectronicSignatureTests(TestCase):
    def setUp(self):
        self.password = "Str0ng-Pass!23"
        self.user = make_user("signer", role="manager", password=self.password)

    def test_signature_requires_correct_password(self):
        with self.assertRaises(ControlViolation):
            apply_signature(
                user=self.user, meaning=ElectronicSignature.Meaning.CLINICAL_APPROVAL,
                entity_type="laboratory.Order", entity_id="order-1",
                payload={"a": 1}, password="wrong",
            )

    def test_signature_refused_without_password(self):
        with self.assertRaises(ControlViolation):
            apply_signature(
                user=self.user, meaning=ElectronicSignature.Meaning.CLINICAL_APPROVAL,
                entity_type="laboratory.Order", entity_id="order-1", payload={"a": 1},
            )

    def test_valid_signature_captures_manifest_and_binds_to_record(self):
        signature = apply_signature(
            user=self.user, meaning=ElectronicSignature.Meaning.CLINICAL_APPROVAL,
            entity_type="laboratory.Order", entity_id="order-1",
            payload={"accession": "2026-01-01-0001"}, password=self.password,
        )
        self.assertTrue(signature.reauthenticated)
        self.assertEqual(signature.signer_printed_name, self.user.get_full_name())
        self.assertEqual(len(signature.record_hash), 64)
        self.assertIn("Clinically approved by", signature.manifest)
        recorder.flush(timeout=5)
        self.assertIsNotNone(signature.audit_sequence)
        self.assertTrue(AuditEvent.objects.filter(sequence=signature.audit_sequence).exists())

    def test_signature_hash_changes_with_content(self):
        first = apply_signature(
            user=self.user, meaning=ElectronicSignature.Meaning.REVIEW,
            entity_type="laboratory.Order", entity_id="o1",
            payload={"value": "5.0"}, password=self.password,
        )
        second = apply_signature(
            user=self.user, meaning=ElectronicSignature.Meaning.REVIEW,
            entity_type="laboratory.Order", entity_id="o2",
            payload={"value": "5.1"}, password=self.password,
        )
        self.assertNotEqual(first.record_hash, second.record_hash)

    def test_signatures_cannot_be_deleted(self):
        signature = apply_signature(
            user=self.user, meaning=ElectronicSignature.Meaning.REVIEW,
            entity_type="laboratory.Order", entity_id="o1",
            payload={"v": 1}, password=self.password,
        )
        with self.assertRaises(RuntimeError):
            signature.delete()

    @override_settings(REQUIRE_REAUTH_FOR_SIGNATURE=False)
    def test_reauth_can_be_disabled_but_is_recorded_as_such(self):
        signature = apply_signature(
            user=self.user, meaning=ElectronicSignature.Meaning.REVIEW,
            entity_type="laboratory.Order", entity_id="o1", payload={"v": 1},
        )
        self.assertFalse(signature.reauthenticated)


class AccountSecurityTests(TestCase):
    def setUp(self):
        self.password = "Str0ng-Pass!23"
        self.user = make_user("locked", password=self.password)

    @override_settings(ACCOUNT_LOCKOUT_THRESHOLD=3, ACCOUNT_LOCKOUT_MINUTES=30)
    def test_account_locks_after_threshold(self):
        for _ in range(3):
            register_failed_login(self.user.username)
        self.assertFalse(check_account_available(self.user).allowed)

    @override_settings(ACCOUNT_LOCKOUT_THRESHOLD=3)
    def test_account_available_below_threshold(self):
        register_failed_login(self.user.username)
        self.assertTrue(check_account_available(self.user).allowed)

    def test_password_reuse_is_refused(self):
        record_password_change(self.user)
        check = check_password_reuse(self.user, self.password)
        self.assertFalse(check.allowed)

    @override_settings(PASSWORD_EXPIRY_DAYS=90)
    def test_password_expiry_is_computed(self):
        state = AccountSecurityState.objects.create(user=self.user)
        self.assertFalse(state.password_expired)
        state.password_changed_at = timezone.now() - timedelta(days=91)
        state.save()
        self.assertTrue(state.password_expired)


class CapaTests(TestCase):
    def test_reference_is_sequential_per_year(self):
        user = make_user("qm", role="manager")
        first = raise_capa(title="QC failure", category="qc_failure",
                           description="1-3s violation", raised_by=user)
        second = raise_capa(title="PT failure", category="pt_failure",
                            description="Unacceptable", raised_by=user)
        year = timezone.localdate().year
        self.assertEqual(first.reference, f"CAPA-{year}-0001")
        self.assertEqual(second.reference, f"CAPA-{year}-0002")
        self.assertFalse(first.is_overdue)


class AmendedReportTests(TestCase):
    """CAP: a corrected report retains the original and is signed."""

    def setUp(self):
        from apps.common.constants import AuditAction
        from apps.laboratory.services import create_order, save_results

        self.password = PASSWORD if (PASSWORD := "Str0ng-Pass!23") else ""
        self.tech = make_user("amend-tech", password=self.password)
        self.senior = make_user("amend-senior", role="manager", password=self.password)
        self.test = make_test(code="AMD")
        grant_competency(self.tech, test=self.test)
        grant_competency(self.senior, test=self.test)
        passing_qc(self.test)

        patient = make_patient(mrn="MRN-AMEND")
        self.order = create_order(patient=patient, tests=[self.test], ordered_by="Dr A")
        save_results(order=self.order, values={self.test.id: "5.0"}, user=self.tech)
        save_results(order=self.order, values={self.test.id: "5.0"}, user=self.senior,
                     action=AuditAction.CLINICAL_VERIFY, password=self.password)
        self.result = self.order.results.get(test_key=self.test.id)

    def test_amendment_retains_the_original_and_signs_the_change(self):
        from apps.laboratory.services import amend_report

        amendment = amend_report(
            order=self.order, result=self.result, corrected_value="7.4",
            reason="transcription", narrative="Transposed digits at entry.",
            user=self.senior, password=self.password, notified_method="phone",
        )
        self.assertEqual(amendment.original_value, "5.0")
        self.assertEqual(amendment.corrected_value, "7.4")
        self.assertEqual(amendment.version, 2)
        self.assertIsNotNone(amendment.signature)
        self.assertTrue(amendment.clinician_notified)

        self.result.refresh_from_db()
        self.assertEqual(self.result.value, "7.4")

    def test_amendment_opens_a_nonconformance(self):
        from apps.laboratory.services import amend_report

        amendment = amend_report(
            order=self.order, result=self.result, corrected_value="9.1",
            reason="analytical", narrative="Instrument drift found on review.",
            user=self.senior, password=self.password, notified_method="phone",
        )
        self.assertIsNotNone(amendment.corrective_action)
        self.assertTrue(amendment.corrective_action.patient_impact)

    def test_amendment_requires_the_signer_password(self):
        from apps.laboratory.services import amend_report

        with self.assertRaises(ControlViolation):
            amend_report(
                order=self.order, result=self.result, corrected_value="7.4",
                reason="transcription", narrative="x", user=self.senior, password="wrong",
            )
        self.result.refresh_from_db()
        self.assertEqual(self.result.value, "5.0")

    def test_versions_increment_across_amendments(self):
        from apps.laboratory.services import amend_report

        first = amend_report(order=self.order, result=self.result, corrected_value="6.0",
                             reason="transcription", narrative="a", user=self.senior,
                             password=self.password, notified_method="phone")
        second = amend_report(order=self.order, result=self.result, corrected_value="6.5",
                              reason="analytical", narrative="b", user=self.senior,
                              password=self.password, notified_method="phone")
        self.assertEqual((first.version, second.version), (2, 3))
