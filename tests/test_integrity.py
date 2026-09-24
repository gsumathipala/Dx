"""Workflow integrity checks, and the badge rendering they exist alongside.

These tests do two things: prove each check fires on the condition it names,
and — just as important — prove it stays quiet on the legitimate cases that
look similar. A check that cries wolf gets switched off, and then the real
finding goes unseen.
"""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.common.constants import OrderStatus
from apps.common.templatetags.dx import flag_badge, status_badge
from apps.laboratory.models import Result, Specimen
from apps.operations import integrity
from tests.factories import make_order, make_patient, make_test, make_user


def codes(findings) -> set[str]:
    return {finding.code for finding in findings}


class AccessioningCheckTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])

    def test_a_result_with_no_specimen_is_an_error(self):
        Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id, value="5.0"
        )
        self.assertIn("ORDER-NO-SPECIMEN", codes(integrity.check_accessioning()))

    def test_an_order_awaiting_collection_is_not_flagged(self):
        """No specimen yet is the normal state of a new request, not a defect."""
        self.assertNotIn("ORDER-NO-SPECIMEN", codes(integrity.check_accessioning()))

    def test_a_resulted_order_with_a_specimen_is_not_flagged(self):
        Specimen.objects.create(order=self.order, type="Serum")
        Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id, value="5.0"
        )
        self.assertNotIn("ORDER-NO-SPECIMEN", codes(integrity.check_accessioning()))

    def test_a_completed_order_with_nothing_in_it_is_an_error(self):
        self.order.status = OrderStatus.COMPLETED
        self.order.save(update_fields=["status"])
        self.assertIn("ORDER-COMPLETE-EMPTY", codes(integrity.check_accessioning()))


class ResultCheckTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])
        Specimen.objects.create(order=self.order, type="Serum")

    def test_a_verified_result_naming_nobody_is_an_error(self):
        Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id, value="5.0",
            status=OrderStatus.CLINICALLY_VERIFIED, clinical_verified_by=None,
        )
        self.assertIn("RESULT-UNATTRIBUTED", codes(integrity.check_results()))

    def test_the_narrative_report_row_is_not_flagged(self):
        """REPORT is a pseudo-result carrying the comment; it has no verifier."""
        Result.objects.create(
            order=self.order, test_key=Result.REPORT_TEST_ID,
            comments="Renal function deteriorating.",
            status=OrderStatus.CLINICALLY_VERIFIED, clinical_verified_by=None,
        )
        self.assertNotIn("RESULT-UNATTRIBUTED", codes(integrity.check_results()))

    def test_a_completed_order_with_an_unverified_analyte_is_an_error(self):
        Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id, value="5.0",
            clinical_verified_by=None,
        )
        self.order.status = OrderStatus.COMPLETED
        self.order.save(update_fields=["status"])
        self.assertIn("ORDER-COMPLETE-UNVERIFIED", codes(integrity.check_results()))

    def test_a_properly_verified_completed_order_is_quiet(self):
        Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id, value="5.0",
            status=OrderStatus.CLINICALLY_VERIFIED, clinical_verified_by="bscientist",
        )
        self.order.status = OrderStatus.COMPLETED
        self.order.save(update_fields=["status"])
        found = codes(integrity.check_results())
        self.assertNotIn("ORDER-COMPLETE-UNVERIFIED", found)
        self.assertNotIn("RESULT-UNATTRIBUTED", found)

    def test_a_numeric_value_with_an_unpopulated_shadow_column_is_an_error(self):
        """A bulk write that bypasses save() blinds delta checks and every rule."""
        result = Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id, value="5.0"
        )
        Result.objects.filter(pk=result.pk).update(numeric_value=None)
        self.assertIn("RESULT-NUMERIC-DRIFT", codes(integrity.check_results()))

    def test_a_genuinely_non_numeric_result_is_not_flagged(self):
        Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id,
            value="haemolysed",
        )
        self.assertNotIn("RESULT-NUMERIC-DRIFT", codes(integrity.check_results()))

    def test_flags_that_disagree_with_the_current_interval_are_reported(self):
        result = Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id, value="5.0"
        )
        result.recompute_flags()
        result.save(update_fields=["result_flags"])

        # The laboratory narrows the interval after the result was released.
        self.test.reference_range = {"min": 3.9, "max": 4.5,
                                     "panicLow": 2.2, "panicHigh": 25.0}
        self.test.save(update_fields=["reference_range"])

        self.assertIn("RESULT-FLAGS-STALE", codes(integrity.check_results()))


class CriticalValueCheckTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])

    def test_an_overdue_unacknowledged_critical_is_an_error(self):
        from apps.clinical.models import CriticalValueNotification

        CriticalValueNotification.objects.create(
            order=self.order, test=self.test, patient=self.patient,
            test_code=self.test.code, value="30", threshold="> 25",
            critical_type=CriticalValueNotification.CriticalType.HIGH,
            created_by="tech",
            escalation_due_at=timezone.now() - timedelta(minutes=5),
        )
        self.assertIn("CRITICAL-OVERDUE", codes(integrity.check_critical_values()))

    def test_a_critically_flagged_result_with_no_notification_is_an_error(self):
        result = Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id, value="30.0"
        )
        result.recompute_flags()
        result.save(update_fields=["result_flags"])

        self.assertIn("Critical High", result.result_flags)
        self.assertIn("CRITICAL-NOT-RAISED", codes(integrity.check_critical_values()))

    def test_a_normal_result_raises_nothing(self):
        result = Result.objects.create(
            order=self.order, test=self.test, test_key=self.test.id, value="5.0"
        )
        result.recompute_flags()
        result.save(update_fields=["result_flags"])
        self.assertEqual(codes(integrity.check_critical_values()), set())


class QualityCheckTests(TestCase):
    def setUp(self):
        self.test = make_test()

    def test_autoverification_without_a_qc_target_is_an_error(self):
        self.test.auto_verify_permitted = True
        self.test.save(update_fields=["auto_verify_permitted"])
        self.assertIn("AUTOVERIFY-NO-QC", codes(integrity.check_quality()))

    def test_autoverification_without_a_reference_interval_is_an_error(self):
        self.test.auto_verify_permitted = True
        self.test.reference_range = None
        self.test.save(update_fields=["auto_verify_permitted", "reference_range"])

        self.assertIn("AUTOVERIFY-NO-INTERVAL", codes(integrity.check_quality()))

    def test_a_properly_configured_analyte_is_quiet(self):
        from tests.factories import passing_qc

        self.test.auto_verify_permitted = True
        self.test.save(update_fields=["auto_verify_permitted"])
        passing_qc(self.test)

        found = codes(integrity.check_quality())
        self.assertNotIn("AUTOVERIFY-NO-QC", found)
        self.assertNotIn("AUTOVERIFY-NO-INTERVAL", found)


class RuleCheckTests(TestCase):
    def setUp(self):
        self.test = make_test()

    def _rule(self, **fields):
        from apps.rules.models import Rule

        defaults = {"name": "R", "active": True}
        defaults.update(fields)
        return Rule.objects.create(**defaults)

    def test_an_active_unapproved_rule_is_a_warning(self):
        self._rule()
        self.assertIn("RULE-UNAPPROVED", codes(integrity.check_rules()))

    def test_an_autoverify_rule_on_an_unpermitted_analyte_is_a_warning(self):
        from apps.rules.models import RuleAction

        rule = self._rule(test=self.test)
        RuleAction.objects.create(rule=rule, kind=RuleAction.Kind.AUTO_VERIFY)
        self.assertIn("RULE-AUTOVERIFY-MISMATCH", codes(integrity.check_rules()))

    def test_an_approved_rule_with_no_conditions_is_a_warning(self):
        rule = self._rule()
        rule.approved_at = timezone.now()
        rule.approved_version = rule.version
        rule.save(update_fields=["approved_at", "approved_version"])

        self.assertIn("RULE-UNCONDITIONAL", codes(integrity.check_rules()))


class InterfaceCheckTests(TestCase):
    def test_a_bidirectional_interface_with_no_code_map_is_an_error(self):
        from apps.interop.models import InstrumentInterface

        InstrumentInterface.objects.create(
            name="ARCH-1", enabled=True, last_message_at=timezone.now(),
            direction=InstrumentInterface.Direction.BIDIRECTIONAL,
            test_code_map={},
        )
        self.assertIn("INTERFACE-NO-CODEMAP", codes(integrity.check_interfaces()))

    def test_a_unidirectional_interface_needs_no_code_map(self):
        from apps.interop.models import InstrumentInterface

        InstrumentInterface.objects.create(
            name="OLD-1", enabled=True, last_message_at=timezone.now(),
            direction=InstrumentInterface.Direction.UNIDIRECTIONAL, test_code_map={},
        )
        self.assertNotIn("INTERFACE-NO-CODEMAP", codes(integrity.check_interfaces()))

    def test_a_phi_scoped_client_with_no_purpose_is_an_error(self):
        from apps.api.models import ApiClient, Scope

        ApiClient.issue(name="Ward board", scopes=[Scope.RESULTS_READ], purpose="")
        self.assertIn("API-NO-PURPOSE", codes(integrity.check_interfaces()))

    def test_a_catalogue_only_client_needs_no_purpose(self):
        from apps.api.models import ApiClient, Scope

        ApiClient.issue(name="Code lookup", scopes=[Scope.CATALOGUE_READ], purpose="")
        self.assertNotIn("API-NO-PURPOSE", codes(integrity.check_interfaces()))


class CatalogueCheckTests(TestCase):
    def test_inverted_limits_are_an_error(self):
        make_test(code="BAD", reference_range={"min": 10, "max": 2})
        self.assertIn("CATALOGUE-INVERTED", codes(integrity.check_catalogue()))

    def test_a_critical_limit_inside_the_reference_interval_is_an_error(self):
        make_test(code="ODD", reference_range={
            "min": 3.9, "max": 5.8, "panicLow": 4.5, "panicHigh": 25.0,
        })
        self.assertIn("CATALOGUE-INVERTED", codes(integrity.check_catalogue()))

    def test_a_sane_catalogue_entry_is_quiet(self):
        make_test()
        self.assertNotIn("CATALOGUE-INVERTED", codes(integrity.check_catalogue()))

    def test_a_test_with_no_interval_is_a_warning_not_an_error(self):
        # The factory substitutes a default for None, so clear it afterwards.
        culture = make_test(code="CULT")
        culture.reference_range = None
        culture.save(update_fields=["reference_range"])
        findings = {f.code: f for f in integrity.check_catalogue()}
        self.assertIn("CATALOGUE-NO-INTERVAL", findings)
        self.assertEqual(findings["CATALOGUE-NO-INTERVAL"].severity, integrity.WARN)


class ContinuityCheckTests(TestCase):
    def test_no_downtime_pack_is_an_error(self):
        self.assertIn("DOWNTIME-NO-PACK", codes(integrity.check_operations()))

    def test_an_unreconciled_outage_is_an_error(self):
        from apps.operations import continuity

        user = make_user("mgr", role="manager")
        event = continuity.declare(kind="unplanned", reason="Power", user=user)
        continuity.end(event, user=user, recovery_notes="Restored.")

        self.assertIn("DOWNTIME-UNRECONCILED", codes(integrity.check_operations()))

    def test_a_reconciled_outage_is_quiet(self):
        from apps.operations import continuity

        user = make_user("mgr", role="manager")
        event = continuity.declare(kind="unplanned", reason="Power", user=user)
        continuity.end(event, user=user, recovery_notes="Restored.")
        continuity.reconcile(event, user=user, notes="All in.")

        self.assertNotIn("DOWNTIME-UNRECONCILED", codes(integrity.check_operations()))


class RunnerTests(TestCase):
    def test_one_failing_check_does_not_hide_the_others(self):
        from unittest.mock import patch

        def explode():
            raise RuntimeError("boom")

        broken = (("test catalogue", explode),) + tuple(
            entry for entry in integrity.CHECKS if entry[0] != "test catalogue"
        )
        with patch.object(integrity, "CHECKS", broken):
            findings, failures = integrity.run_all()

        self.assertIn("test catalogue", failures)
        self.assertIn("CHECK-FAILED", codes(findings))
        # The audit check still ran.
        self.assertTrue({"AUDIT-OK", "AUDIT-TRIGGERS"} & codes(findings))

    def test_the_command_exits_non_zero_on_an_error(self):
        from django.core.management import call_command

        make_test(code="BAD", reference_range={"min": 10, "max": 2})
        with self.assertRaises(SystemExit) as raised:
            call_command("check_workflows", quiet=True, verbosity=0)
        self.assertEqual(raised.exception.code, 1)

    def test_the_command_can_be_told_not_to_fail(self):
        from django.core.management import call_command

        make_test(code="BAD", reference_range={"min": 10, "max": 2})
        call_command("check_workflows", fail_on="never", verbosity=0)

    def test_json_output_is_machine_readable(self):
        import json
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("check_workflows", json=True, fail_on="never", stdout=out)
        payload = json.loads(out.getvalue())
        self.assertIn("counts", payload)
        self.assertIn("findings", payload)


class BadgeRenderingTests(TestCase):
    """Colour is never the only carrier, and a critical is never muted."""

    def test_a_critical_flag_is_not_rendered_in_the_muted_style(self):
        rendered = status_badge("Critical High")
        self.assertIn("badge-critical", rendered)
        self.assertNotIn("badge-muted", rendered)

    def test_a_critical_flag_carries_a_non_colour_marker(self):
        self.assertIn("↑↑", status_badge("Critical High"))
        self.assertIn("↓↓", status_badge("Critical Low"))

    def test_an_abnormal_flag_is_distinguishable_from_a_critical_one(self):
        self.assertNotEqual(status_badge("High"), status_badge("Critical High"))
        self.assertIn("badge-warn", status_badge("High"))

    def test_the_full_text_is_always_present(self):
        for flag in ("Normal", "Low", "High", "Critical Low", "Critical High"):
            with self.subTest(flag=flag):
                self.assertIn(flag, status_badge(flag))

    def test_critical_high_and_critical_low_differ_in_the_compact_form(self):
        """They rendered as an identical 'C' on the cumulative report."""
        self.assertNotEqual(flag_badge("Critical High"), flag_badge("Critical Low"))
        self.assertIn(">HH<", flag_badge("Critical High"))
        self.assertIn(">LL<", flag_badge("Critical Low"))

    def test_the_compact_form_keeps_the_full_name_as_a_title(self):
        self.assertIn('title="Critical High"', flag_badge("Critical High"))

    def test_the_compact_abbreviations_match_what_hl7_export_emits(self):
        """The screen and the interchange should not disagree."""
        from apps.interop.services import INTERPRETATION
        from apps.common.templatetags.dx import FLAG_ABBREVIATIONS

        for flag, (hl7_code, _display) in INTERPRETATION.items():
            with self.subTest(flag=flag):
                self.assertEqual(FLAG_ABBREVIATIONS[flag], hl7_code)

    def test_an_unknown_value_still_renders_readably(self):
        self.assertIn("Whatever", status_badge("Whatever"))


class SeededDataIsSelfConsistentTests(TestCase):
    """A freshly seeded database must pass its own integrity checks.

    The demonstration data is the first thing anybody downloading this runs. If
    it does not satisfy the checks the system ships with, either the data or
    the checks are wrong — and an evaluator has no way to tell which.
    """

    def test_seed_demo_produces_no_integrity_errors(self):
        from django.core.management import call_command

        call_command("seed_demo", verbosity=0)
        findings, failures = integrity.run_all()

        self.assertEqual(failures, {})
        errors = [f for f in findings if f.severity == integrity.ERROR]
        # The audit triggers are dropped by the test runner so it can TRUNCATE,
        # and no downtime pack exists in a test database. Neither is about the
        # seeded data, which is what this test is asserting.
        expected = {"AUDIT-TRIGGERS", "DOWNTIME-NO-PACK"}
        unexpected = [f"{f.code}: {f.title} — {f.examples}"
                      for f in errors if f.code not in expected]
        self.assertEqual(unexpected, [], f"seeded data is not self-consistent: {unexpected}")

    def test_every_seeded_order_with_results_has_a_specimen(self):
        """A result recorded against nothing measurable is a broken custody chain."""
        from django.core.management import call_command

        from apps.laboratory.models import Order

        call_command("seed_demo", verbosity=0)
        stranded = [
            order.accession_number
            for order in Order.objects.filter(results__isnull=False).distinct()
            if not order.specimens.exists()
        ]
        self.assertEqual(stranded, [])
