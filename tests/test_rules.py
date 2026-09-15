"""The rules engine, and the guardrails around automatic verification.

The autoverification tests matter more than the rest of the file put together.
Each one asserts that a specific class of result is *not* released — a critical
value, a delta flag, an out-of-range result, a failed QC. If one of these ever
starts passing by returning True, a laboratory somewhere reports a potassium of
7.2 to nobody.
"""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.clinical.models import DeltaCheckFlag, DeltaCheckRule
from apps.common.constants import OrderStatus
from apps.compliance.models import ElectronicSignature
from apps.laboratory.models import Result
from apps.operations.models import ExceptionItem, ExceptionSource
from apps.quality.models import QcRun
from apps.rules import autoverify
from apps.rules.engine import build_facts, evaluate_condition, matches, run_for_result
from apps.rules.models import Rule, RuleAction, RuleCondition, RuleExecution
from tests.factories import (
    grant_competency, make_order, make_patient, make_test, make_user, passing_qc,
)


def make_rule(name="Rule", *, test=None, approved=True, trigger=Rule.Trigger.RESULT_ENTERED,
              priority=100, stop_on_match=False):
    rule = Rule.objects.create(
        name=name, test=test, trigger=trigger, priority=priority,
        stop_on_match=stop_on_match,
    )
    if approved:
        rule.approved_at = timezone.now()
        rule.approved_version = rule.version
        rule.save(update_fields=["approved_at", "approved_version"])
    return rule


def add_condition(rule, subject, operator, value="", value_to="", group=0):
    return RuleCondition.objects.create(
        rule=rule, subject=subject, operator=operator, value=str(value),
        value_to=str(value_to), group=group,
    )


def add_action(rule, kind, **fields):
    return RuleAction.objects.create(rule=rule, kind=kind, **fields)


def enter(order, test, value):
    result = Result.objects.create(
        order=order, test=test, test_key=test.id, value=str(value),
        status=OrderStatus.RESULTED, entered_by="tech",
    )
    result.recompute_flags()
    result.save(update_fields=["result_flags"])
    return result


class ConditionEvaluationTests(TestCase):
    """The comparison layer, tested as a pure function over a fact dictionary."""

    def setUp(self):
        self.rule = make_rule()

    def test_numeric_comparison(self):
        condition = add_condition(self.rule, RuleCondition.Subject.RESULT_VALUE, "gt", 5)
        self.assertTrue(evaluate_condition(condition, {"result.value": 6.0}))
        self.assertFalse(evaluate_condition(condition, {"result.value": 4.0}))

    def test_between_is_inclusive(self):
        condition = add_condition(self.rule, RuleCondition.Subject.PATIENT_AGE_YEARS,
                                  "between", 18, 65)
        self.assertTrue(evaluate_condition(condition, {"patient.age_years": 18}))
        self.assertTrue(evaluate_condition(condition, {"patient.age_years": 65}))
        self.assertFalse(evaluate_condition(condition, {"patient.age_years": 66}))

    def test_missing_fact_never_matches(self):
        """Silence is not evidence of normality."""
        condition = add_condition(self.rule, RuleCondition.Subject.PRIOR_VALUE, "lt", 5)
        self.assertFalse(evaluate_condition(condition, {"prior.value": None}))

    def test_missing_fact_does_match_is_blank(self):
        condition = add_condition(self.rule, RuleCondition.Subject.PRIOR_VALUE, "blank")
        self.assertTrue(evaluate_condition(condition, {"prior.value": None}))

    def test_text_comparison_ignores_case(self):
        condition = add_condition(self.rule, RuleCondition.Subject.PATIENT_SEX, "eq", "f")
        self.assertTrue(evaluate_condition(condition, {"patient.sex": "F"}))

    def test_list_fact_is_a_membership_test(self):
        condition = add_condition(self.rule, RuleCondition.Subject.ORDER_ICD10, "in", "E11.9,E87.1")
        self.assertTrue(evaluate_condition(condition, {"order.icd10": ["E87.1"]}))
        self.assertFalse(evaluate_condition(condition, {"order.icd10": ["I10"]}))

    def test_boolean_fact(self):
        condition = add_condition(self.rule, RuleCondition.Subject.RESULT_IS_CRITICAL, "eq", "true")
        self.assertTrue(evaluate_condition(condition, {"result.is_critical": True}))
        self.assertFalse(evaluate_condition(condition, {"result.is_critical": False}))

    def test_groups_are_anded_within_and_ored_across(self):
        add_condition(self.rule, RuleCondition.Subject.RESULT_VALUE, "gt", 5, group=0)
        add_condition(self.rule, RuleCondition.Subject.PATIENT_SEX, "eq", "F", group=0)
        add_condition(self.rule, RuleCondition.Subject.ORDER_PRIORITY, "eq", "STAT", group=1)

        self.assertTrue(matches(self.rule, {
            "result.value": 6, "patient.sex": "F", "order.priority": "Routine"}))
        self.assertFalse(matches(self.rule, {
            "result.value": 6, "patient.sex": "M", "order.priority": "Routine"}))
        # The second group alone is enough.
        self.assertTrue(matches(self.rule, {
            "result.value": 1, "patient.sex": "M", "order.priority": "STAT"}))

    def test_a_rule_with_no_conditions_matches_everything(self):
        self.assertTrue(matches(make_rule("Bare"), {}))


class FactGatheringTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])

    def test_facts_describe_the_result_and_the_patient(self):
        result = enter(self.order, self.test, 5.0)
        facts = build_facts(self.order, self.test, result)

        self.assertEqual(facts[RuleCondition.Subject.RESULT_VALUE], 5.0)
        self.assertEqual(facts[RuleCondition.Subject.TEST_CODE], "GLU")
        self.assertEqual(facts[RuleCondition.Subject.PATIENT_SEX], "F")
        self.assertEqual(facts[RuleCondition.Subject.RESULT_POSITION], "within")
        self.assertFalse(facts[RuleCondition.Subject.RESULT_IS_CRITICAL])

    def test_position_reflects_the_reference_interval(self):
        result = enter(self.order, self.test, 9.0)
        facts = build_facts(self.order, self.test, result)
        self.assertEqual(facts[RuleCondition.Subject.RESULT_POSITION], "above")

    def test_prior_value_and_delta_come_from_the_patients_history(self):
        earlier = make_order(
            self.patient, [self.test], when=timezone.now() - timedelta(days=3),
            accession="2026-01-01-9001",
        )
        enter(earlier, self.test, 4.0)
        result = enter(self.order, self.test, 6.0)

        facts = build_facts(self.order, self.test, result)
        self.assertEqual(facts[RuleCondition.Subject.PRIOR_VALUE], 4.0)
        self.assertEqual(facts[RuleCondition.Subject.DELTA_ABSOLUTE], 2.0)
        self.assertAlmostEqual(facts[RuleCondition.Subject.DELTA_PERCENT], 50.0)

    def test_instrument_entry_is_distinguishable_from_manual(self):
        result = enter(self.order, self.test, 5.0)
        facts = build_facts(self.order, self.test, result, entered_by="instrument:ARCH-1")
        self.assertEqual(facts[RuleCondition.Subject.ENTERED_BY_SOURCE], "instrument")


class ApprovalTests(TestCase):
    def test_an_unapproved_rule_does_not_fire(self):
        test = make_test()
        rule = make_rule("Draft", test=test, approved=False)
        add_action(rule, RuleAction.Kind.APPEND_COMMENT, text="Should not appear")

        order = make_order(make_patient(), [test])
        result = enter(order, test, 5.0)
        outcome = run_for_result(
            order, test, result, trigger=Rule.Trigger.RESULT_ENTERED
        )

        self.assertEqual(outcome["executions"], [])
        result.refresh_from_db()
        self.assertIsNone(result.comments)

    def test_editing_an_approved_rule_withdraws_its_approval(self):
        rule = make_rule("Live")
        self.assertTrue(rule.is_approved)

        rule.bump_version()
        rule.save()

        self.assertEqual(rule.version, 2)
        self.assertFalse(rule.is_approved)
        self.assertFalse(rule.is_live)


class ActionTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])

    def _fire(self, result, entered_by=""):
        return run_for_result(
            self.order, self.test, result,
            trigger=Rule.Trigger.RESULT_ENTERED, entered_by=entered_by,
        )

    def test_a_comment_is_appended_and_attributed(self):
        rule = make_rule("Hyperglycaemia note", test=self.test)
        add_condition(rule, RuleCondition.Subject.RESULT_VALUE, "gt", 7)
        add_action(rule, RuleAction.Kind.APPEND_COMMENT,
                   text="Consider a fasting sample.")

        result = enter(self.order, self.test, 9.0)
        self._fire(result)

        result.refresh_from_db()
        self.assertIn("Consider a fasting sample.", result.comments)
        self.assertIn("[Hyperglycaemia note]", result.comments)

    def test_the_same_comment_is_not_appended_twice(self):
        rule = make_rule("Note", test=self.test)
        add_action(rule, RuleAction.Kind.APPEND_COMMENT, text="Repeat sample.")

        result = enter(self.order, self.test, 9.0)
        self._fire(result)
        self._fire(result)

        result.refresh_from_db()
        self.assertEqual(result.comments.count("Repeat sample."), 1)

    def test_a_rule_can_add_a_flag(self):
        rule = make_rule("Flagger", test=self.test)
        add_action(rule, RuleAction.Kind.SET_FLAG, flag="Review")

        result = enter(self.order, self.test, 5.0)
        self._fire(result)

        result.refresh_from_db()
        self.assertIn("Review", result.result_flags)

    def test_a_rule_can_add_a_follow_on_test(self):
        follow_on = make_test(code="HBA1C", name="HbA1c")
        rule = make_rule("Reflex", test=self.test)
        add_condition(rule, RuleCondition.Subject.RESULT_VALUE, "gt", 7)
        add_action(rule, RuleAction.Kind.ADD_TEST, add_test=follow_on)

        result = enter(self.order, self.test, 11.0)
        self._fire(result)

        self.assertTrue(self.order.tests.filter(code="HBA1C").exists())

    def test_a_rule_can_raise_an_exception_queue_item(self):
        rule = make_rule("Escalate", test=self.test)
        add_action(rule, RuleAction.Kind.RAISE_EXCEPTION,
                   text="Check the analyser", severity="high")

        result = enter(self.order, self.test, 5.0)
        self._fire(result)

        item = ExceptionItem.objects.get(source=ExceptionSource.RULE)
        self.assertEqual(item.severity, "high")
        self.assertEqual(item.order_id, self.order.pk)

    def test_stop_on_match_prevents_later_rules_running(self):
        first = make_rule("First", test=self.test, priority=1, stop_on_match=True)
        add_action(first, RuleAction.Kind.SET_FLAG, flag="A")
        second = make_rule("Second", test=self.test, priority=2)
        add_action(second, RuleAction.Kind.APPEND_COMMENT, text="Never reached")

        result = enter(self.order, self.test, 5.0)
        self._fire(result)

        result.refresh_from_db()
        self.assertIn("A", result.result_flags)
        self.assertIsNone(result.comments)

    def test_a_failing_action_does_not_lose_the_result(self):
        """A broken rule is a rule problem, never a patient-safety problem."""
        rule = make_rule("Broken", test=self.test)
        # add_test is required by this action kind and deliberately absent.
        add_action(rule, RuleAction.Kind.ADD_TEST, add_test=None)

        result = enter(self.order, self.test, 5.0)
        self._fire(result)

        result.refresh_from_db()
        self.assertEqual(result.value, "5.0")

    def test_an_execution_records_the_facts_it_saw(self):
        rule = make_rule("Recorder", test=self.test)
        add_action(rule, RuleAction.Kind.SET_FLAG, flag="X")

        result = enter(self.order, self.test, 5.0)
        self._fire(result)

        execution = RuleExecution.objects.get(rule=rule)
        self.assertEqual(execution.facts["result.value"], 5.0)
        self.assertEqual(execution.rule_version, rule.version)


class AutoVerificationGuardrailTests(TestCase):
    """Every one of these asserts that a result is *not* released."""

    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.test.auto_verify_permitted = True
        self.test.save(update_fields=["auto_verify_permitted"])
        self.order = make_order(self.patient, [self.test])
        passing_qc(self.test)

        # Deliberately unconditional: these tests prove that the *guardrails*
        # refuse, not that a cleverly-written condition happened to exclude the
        # dangerous case. A laboratory will write a rule this broad, and the
        # system has to be safe when they do.
        self.rule = make_rule("Release routine chemistry", test=self.test)
        add_action(self.rule, RuleAction.Kind.AUTO_VERIFY)

    def _attempt(self, result):
        outcome = run_for_result(
            self.order, self.test, result, trigger=Rule.Trigger.RESULT_ENTERED
        )
        return autoverify.attempt(self.order, self.test, result, outcome["executions"])

    def test_a_normal_result_with_good_qc_is_released(self):
        result = enter(self.order, self.test, 5.0)
        self.assertTrue(self._attempt(result))

        result.refresh_from_db()
        self.assertEqual(result.status, OrderStatus.CLINICALLY_VERIFIED)
        self.assertEqual(result.clinical_verified_by, f"rule:{self.rule.name}")

    def test_the_signature_is_attributed_to_the_rule_not_a_person(self):
        result = enter(self.order, self.test, 5.0)
        self._attempt(result)

        signature = ElectronicSignature.objects.get(
            entity_type="laboratory.Result", entity_id=str(result.pk)
        )
        self.assertIsNone(signature.signer_id)
        self.assertEqual(signature.automated_rule_id, self.rule.pk)
        self.assertEqual(signature.signer_role, "rule")
        self.assertEqual(signature.meaning, ElectronicSignature.Meaning.AUTO_VERIFICATION)
        self.assertIn("no human review", signature.manifest)

    def test_a_critical_value_is_never_released(self):
        result = enter(self.order, self.test, 30.0)  # panicHigh is 25.0
        self.assertFalse(self._attempt(result))

        result.refresh_from_db()
        self.assertNotEqual(result.status, OrderStatus.CLINICALLY_VERIFIED)
        execution = RuleExecution.objects.get(rule=self.rule)
        self.assertTrue(any("Critical" in reason for reason in execution.refusals))

    def test_a_result_outside_the_reference_interval_is_never_released(self):
        result = enter(self.order, self.test, 9.0)
        self.assertFalse(self._attempt(result))
        self.assertTrue(any(
            "reference interval" in reason
            for reason in RuleExecution.objects.get(rule=self.rule).refusals
        ))

    def test_a_delta_flagged_result_is_never_released(self):
        DeltaCheckRule.objects.create(
            test=self.test, test_code=self.test.code, threshold=10,
            delta_type=DeltaCheckRule.DeltaType.PERCENT, lookback_days=30,
        )
        result = enter(self.order, self.test, 5.0)
        DeltaCheckFlag.objects.create(
            order=self.order, test=self.test,
            rule=DeltaCheckRule.objects.first(),
            previous_value=1.0, current_value=5.0, delta_absolute=4.0,
        )

        self.assertFalse(self._attempt(result))
        self.assertTrue(any(
            "delta" in reason.lower()
            for reason in RuleExecution.objects.get(rule=self.rule).refusals
        ))

    def test_failed_quality_control_blocks_release(self):
        QcRun.objects.filter(definition__test_code=self.test.code).update(
            status=QcRun.Status.FAIL
        )
        result = enter(self.order, self.test, 5.0)
        self.assertFalse(self._attempt(result))
        self.assertTrue(any(
            "Quality control" in reason
            for reason in RuleExecution.objects.get(rule=self.rule).refusals
        ))

    def test_absent_quality_control_blocks_release(self):
        QcRun.objects.all().delete()
        result = enter(self.order, self.test, 5.0)
        self.assertFalse(self._attempt(result))

    def test_an_analyte_not_approved_for_autoverification_is_refused(self):
        self.test.auto_verify_permitted = False
        self.test.save(update_fields=["auto_verify_permitted"])

        result = enter(self.order, self.test, 5.0)
        self.assertFalse(self._attempt(result))
        self.assertTrue(any(
            "not approved for autoverification" in reason
            for reason in RuleExecution.objects.get(rule=self.rule).refusals
        ))

    def test_a_non_numeric_result_is_refused(self):
        result = enter(self.order, self.test, "haemolysed")
        self.assertFalse(self._attempt(result))

    def test_a_rejected_specimen_blocks_release(self):
        from apps.laboratory.models import Specimen, SpecimenReceiving

        specimen = Specimen.objects.create(order=self.order, type="Serum")
        SpecimenReceiving.objects.create(
            specimen=specimen, order=self.order, received_by="tech",
            condition=SpecimenReceiving.Condition.MARGINAL,
            status=SpecimenReceiving.Status.ACCEPTED,
        )
        result = enter(self.order, self.test, 5.0)
        self.assertFalse(self._attempt(result))

    def test_an_open_exception_on_the_order_blocks_release(self):
        from apps.operations.exceptions import raise_exception

        raise_exception(
            source=ExceptionSource.MANUAL, source_key="test:1",
            title="Something is wrong", order=self.order,
        )
        result = enter(self.order, self.test, 5.0)
        self.assertFalse(self._attempt(result))

    def test_the_installation_switch_stops_everything(self):
        with self.settings(RULES_ALLOW_AUTO_VERIFICATION=False):
            result = enter(self.order, self.test, 5.0)
            self.assertFalse(self._attempt(result))

    def test_every_refusal_is_listed_not_just_the_first(self):
        """A laboratory tuning a rule set needs all the blockers at once."""
        self.test.auto_verify_permitted = False
        self.test.save(update_fields=["auto_verify_permitted"])
        QcRun.objects.all().delete()

        result = enter(self.order, self.test, 30.0)
        decision = autoverify.assess(self.order, self.test, result)

        self.assertFalse(decision.allowed)
        self.assertGreaterEqual(len(decision.refusals), 3)

    def test_the_order_closes_when_every_analyte_is_released(self):
        result = enter(self.order, self.test, 5.0)
        self._attempt(result)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertIsNotNone(self.order.completed_at)

    def test_an_order_with_an_unverified_analyte_stays_open(self):
        other = make_test(code="K", name="Potassium")
        self.order.tests.add(other)
        Result.objects.create(
            order=self.order, test=other, test_key=other.id, value="4.0",
            status=OrderStatus.RESULTED, entered_by="tech",
        )

        result = enter(self.order, self.test, 5.0)
        self._attempt(result)

        self.order.refresh_from_db()
        self.assertNotEqual(self.order.status, OrderStatus.COMPLETED)


class OverrideTests(TestCase):
    def setUp(self):
        self.user = make_user("mgr", role="manager")
        self.patient = make_patient()
        self.test = make_test()
        self.test.auto_verify_permitted = True
        self.test.save(update_fields=["auto_verify_permitted"])
        self.order = make_order(self.patient, [self.test])
        passing_qc(self.test)

        self.rule = make_rule("Releaser", test=self.test)
        add_action(self.rule, RuleAction.Kind.AUTO_VERIFY)

        self.result = enter(self.order, self.test, 5.0)
        outcome = run_for_result(
            self.order, self.test, self.result, trigger=Rule.Trigger.RESULT_ENTERED
        )
        autoverify.attempt(self.order, self.test, self.result, outcome["executions"])
        self.execution = RuleExecution.objects.get(rule=self.rule)

    def test_an_override_returns_the_result_to_the_worklist(self):
        autoverify.override(self.execution, user=self.user, reason="Looks implausible.")

        self.result.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.result.status, OrderStatus.RESULTED)
        self.assertIsNone(self.result.clinical_verified_by)
        self.assertNotEqual(self.order.status, OrderStatus.COMPLETED)

    def test_the_original_signature_is_retained(self):
        autoverify.override(self.execution, user=self.user, reason="Checking.")

        self.assertTrue(ElectronicSignature.objects.filter(
            automated_rule=self.rule
        ).exists())

    def test_an_override_needs_a_reason(self):
        from apps.compliance.services import ControlViolation

        with self.assertRaises(ControlViolation):
            autoverify.override(self.execution, user=self.user, reason="   ")

    def test_a_result_cannot_be_overridden_twice(self):
        from apps.compliance.services import ControlViolation

        autoverify.override(self.execution, user=self.user, reason="First.")
        self.execution.refresh_from_db()
        with self.assertRaises(ControlViolation):
            autoverify.override(self.execution, user=self.user, reason="Again.")


class ResultEntryIntegrationTests(TestCase):
    """Rules must run as part of ordinary result entry, not only when called."""

    def setUp(self):
        self.user = make_user("bms", role="scientist")
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])
        grant_competency(self.user, self.test)
        passing_qc(self.test)

    def test_entering_a_result_fires_the_rules(self):
        from apps.laboratory.services import save_results

        rule = make_rule("Entry note", test=self.test)
        add_condition(rule, RuleCondition.Subject.RESULT_VALUE, "gt", 7)
        add_action(rule, RuleAction.Kind.APPEND_COMMENT, text="Fasting sample advised.")

        save_results(order=self.order, values={self.test.id: "9.0"}, user=self.user)

        result = Result.objects.get(order=self.order, test_key=self.test.id)
        self.assertIn("Fasting sample advised.", result.comments)

    def test_autoverification_runs_through_result_entry(self):
        from apps.laboratory.services import save_results

        self.test.auto_verify_permitted = True
        self.test.save(update_fields=["auto_verify_permitted"])
        rule = make_rule("Release", test=self.test)
        add_condition(rule, RuleCondition.Subject.RESULT_POSITION, "eq", "within")
        add_action(rule, RuleAction.Kind.AUTO_VERIFY)

        outcome = save_results(
            order=self.order, values={self.test.id: "5.0"}, user=self.user
        )

        self.assertEqual(len(outcome["autoverified"]), 1)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)

    def test_a_rule_that_raises_does_not_prevent_the_result_being_saved(self):
        from apps.laboratory.services import save_results
        from unittest.mock import patch

        rule = make_rule("Exploder", test=self.test)
        add_action(rule, RuleAction.Kind.SET_FLAG, flag="X")

        with patch("apps.rules.engine.run_for_result", side_effect=RuntimeError("boom")):
            save_results(order=self.order, values={self.test.id: "5.0"}, user=self.user)

        self.assertTrue(Result.objects.filter(order=self.order, value="5.0").exists())


class ScreenRenderTests(TestCase):
    """The detail screens take arguments, so the route smoke test skips them."""

    def setUp(self):
        self.manager = make_user("mgr", role="manager", password="Str0ng-Pass!23")
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])
        passing_qc(self.test)

        self.rule = make_rule("Screen test", test=self.test)
        add_condition(self.rule, RuleCondition.Subject.RESULT_VALUE, "gt", 4)
        add_action(self.rule, RuleAction.Kind.APPEND_COMMENT, text="A note.")

        self.result = enter(self.order, self.test, 5.0)
        run_for_result(
            self.order, self.test, self.result, trigger=Rule.Trigger.RESULT_ENTERED
        )
        self.execution = RuleExecution.objects.get(rule=self.rule)
        self.client.force_login(self.manager)

    def test_the_rule_detail_screen_renders(self):
        from django.urls import reverse

        response = self.client.get(reverse("rules:rule_detail", args=[self.rule.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Screen test")
        self.assertContains(response, "Live (v1)")

    def test_the_simulation_panel_renders(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("rules:rule_detail", args=[self.rule.pk]),
            {"accession_number": self.order.accession_number},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "matches")

    def test_simulating_against_an_unknown_order_says_so(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("rules:rule_detail", args=[self.rule.pk]),
            {"accession_number": "NOPE"},
        )
        self.assertContains(response, "No order with accession number")

    def test_the_execution_detail_screen_renders(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("rules:execution_detail", args=[self.execution.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Screen test")

    def test_the_builder_renders(self):
        from django.urls import reverse

        response = self.client.get(reverse("rules:rule_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Conditions")
        self.assertContains(response, "Actions")

    def test_the_builder_saves_a_rule_with_conditions_and_actions(self):
        from django.urls import reverse

        response = self.client.post(reverse("rules:rule_create"), {
            "name": "Built through the form",
            "description": "",
            "trigger": Rule.Trigger.RESULT_ENTERED,
            "test": self.test.pk,
            "priority": 100,
            "active": "on",
            "conditions-TOTAL_FORMS": "1",
            "conditions-INITIAL_FORMS": "0",
            "conditions-MIN_NUM_FORMS": "0",
            "conditions-MAX_NUM_FORMS": "1000",
            "conditions-0-group": "0",
            "conditions-0-subject": RuleCondition.Subject.RESULT_VALUE,
            "conditions-0-operator": "gt",
            "conditions-0-value": "7",
            "conditions-0-value_to": "",
            "actions-TOTAL_FORMS": "1",
            "actions-INITIAL_FORMS": "0",
            "actions-MIN_NUM_FORMS": "0",
            "actions-MAX_NUM_FORMS": "1000",
            "actions-0-kind": RuleAction.Kind.APPEND_COMMENT,
            "actions-0-text": "Built.",
            "actions-0-flag": "",
            "actions-0-add_test": "",
            "actions-0-recipient_role": "",
            "actions-0-severity": "medium",
        })
        self.assertEqual(response.status_code, 302)

        built = Rule.objects.get(name="Built through the form")
        self.assertEqual(built.conditions.count(), 1)
        self.assertEqual(built.actions.count(), 1)
        # A new rule is a draft, whatever the form said.
        self.assertFalse(built.is_approved)

    def test_a_non_numeric_value_on_a_numeric_subject_is_rejected(self):
        from django.urls import reverse

        response = self.client.post(reverse("rules:rule_create"), {
            "name": "Bad threshold",
            "description": "",
            "trigger": Rule.Trigger.RESULT_ENTERED,
            "priority": 100,
            "active": "on",
            "conditions-TOTAL_FORMS": "1",
            "conditions-INITIAL_FORMS": "0",
            "conditions-MIN_NUM_FORMS": "0",
            "conditions-MAX_NUM_FORMS": "1000",
            "conditions-0-group": "0",
            "conditions-0-subject": RuleCondition.Subject.RESULT_VALUE,
            "conditions-0-operator": "gt",
            "conditions-0-value": "high",
            "conditions-0-value_to": "",
            "actions-TOTAL_FORMS": "0",
            "actions-INITIAL_FORMS": "0",
            "actions-MIN_NUM_FORMS": "0",
            "actions-MAX_NUM_FORMS": "1000",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Rule.objects.filter(name="Bad threshold").exists())

    def test_approving_puts_the_rule_into_service(self):
        from django.urls import reverse

        draft = make_rule("Needs approval", test=self.test, approved=False)
        with self.settings(REQUIRE_REAUTH_FOR_SIGNATURE=False):
            self.client.post(reverse("rules:rule_approve", args=[draft.pk]), {
                "comment": "Simulated against two historic orders.",
            })
        draft.refresh_from_db()
        self.assertTrue(draft.is_approved)
        self.assertEqual(draft.approved_by, self.manager)

    def test_a_scientist_cannot_approve(self):
        from django.urls import reverse

        scientist = make_user("bms2", role="scientist", password="Str0ng-Pass!23")
        self.client.force_login(scientist)
        draft = make_rule("Needs approval", test=self.test, approved=False)

        response = self.client.post(reverse("rules:rule_approve", args=[draft.pk]), {
            "comment": "Trying.",
        })
        draft.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(draft.is_approved)

    def test_the_installer_cannot_reach_the_rules_at_all(self):
        from django.urls import reverse

        installer = make_user("inst", role="installer", password="Str0ng-Pass!23")
        self.client.force_login(installer)
        response = self.client.get(reverse("rules:rule_list"))
        self.assertEqual(response.status_code, 403)
