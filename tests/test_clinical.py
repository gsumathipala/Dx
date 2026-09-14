"""Clinical engine: delta checks, critical values, reflex, ranges, calculations.

Several cases here are regression tests for defects in the original TypeScript
implementation; those are named accordingly.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.clinical.models import (
    CalculatedTest, CriticalValueNotification, DeltaCheckRule,
    DemographicReferenceRange, NotifiableCondition, ReflexRule,
)
from apps.clinical.services import (
    check_critical_value, check_notifiable_conditions, compute_calculated_test,
    evaluate_reflex_rules, find_reference_range, run_delta_checks,
)
from apps.common.constants import ResultFlag
from apps.laboratory.models import Result
from tests.factories import make_order, make_patient, make_test, make_user


class ReferenceRangeEvaluationTests(TestCase):
    def test_two_sided_range(self):
        test = make_test(reference_range={"min": 3.9, "max": 5.8})
        self.assertEqual(test.evaluate(2.0), ResultFlag.LOW)
        self.assertEqual(test.evaluate(4.5), ResultFlag.NORMAL)
        self.assertEqual(test.evaluate(9.0), ResultFlag.HIGH)

    def test_upper_bound_only_range_is_honoured(self):
        """Regression: the original returned Normal unless both bounds existed,
        so a 'cholesterol < 5.2' style range never flagged."""
        test = make_test(code="CHOL", reference_range={"max": 5.2})
        self.assertEqual(test.evaluate(7.0), ResultFlag.HIGH)
        self.assertEqual(test.evaluate(4.0), ResultFlag.NORMAL)

    def test_lower_bound_only_range_is_honoured(self):
        test = make_test(code="HDL", reference_range={"min": 1.0})
        self.assertEqual(test.evaluate(0.6), ResultFlag.LOW)
        self.assertEqual(test.evaluate(1.5), ResultFlag.NORMAL)

    def test_panic_limits_take_precedence(self):
        test = make_test(reference_range={"min": 3.9, "max": 5.8, "panicLow": 2.2, "panicHigh": 25.0})
        self.assertEqual(test.evaluate(1.0), ResultFlag.CRITICAL_LOW)
        self.assertEqual(test.evaluate(30.0), ResultFlag.CRITICAL_HIGH)

    def test_non_numeric_value_is_normal(self):
        test = make_test()
        self.assertEqual(test.evaluate("Not detected"), ResultFlag.NORMAL)

    def test_zero_is_evaluated_not_skipped(self):
        test = make_test(reference_range={"min": 3.9, "max": 5.8})
        self.assertEqual(test.evaluate(0), ResultFlag.LOW)


class DeltaCheckTests(TestCase):
    def setUp(self):
        self.test = make_test()
        self.patient = make_patient()
        self.rule = DeltaCheckRule.objects.create(
            test=self.test, test_code=self.test.code,
            delta_type=DeltaCheckRule.DeltaType.PERCENT, threshold=50,
            direction=DeltaCheckRule.Direction.ANY, lookback_days=30,
        )

    def _result(self, order, value):
        return Result.objects.create(
            order=order, test=self.test, test_key=self.test.id, value=str(value)
        )

    def test_percent_delta_over_threshold_flags(self):
        earlier = make_order(self.patient, [self.test], when=timezone.now() - timedelta(days=2))
        self._result(earlier, 5.0)
        current = make_order(self.patient, [self.test])
        flags = run_delta_checks(current, self.test, 10.0)
        self.assertEqual(len(flags), 1)
        self.assertAlmostEqual(flags[0].delta_percent, 100.0)

    def test_change_below_threshold_does_not_flag(self):
        earlier = make_order(self.patient, [self.test], when=timezone.now() - timedelta(days=2))
        self._result(earlier, 5.0)
        current = make_order(self.patient, [self.test])
        self.assertEqual(run_delta_checks(current, self.test, 5.5), [])

    def test_future_result_is_not_used_as_the_comparator(self):
        """Regression: the original took the five most recent orders regardless
        of whether they preceded the one being resulted."""
        current = make_order(self.patient, [self.test], when=timezone.now() - timedelta(days=1))
        later = make_order(self.patient, [self.test], when=timezone.now())
        self._result(later, 100.0)
        self.assertEqual(run_delta_checks(current, self.test, 5.0), [])

    def test_result_outside_lookback_window_is_ignored(self):
        stale = make_order(self.patient, [self.test], when=timezone.now() - timedelta(days=90))
        self._result(stale, 5.0)
        current = make_order(self.patient, [self.test])
        self.assertEqual(run_delta_checks(current, self.test, 50.0), [])

    def test_identical_value_does_not_trigger_a_decrease_rule(self):
        """Regression: equality was classified as 'decrease' in the original."""
        self.rule.direction = DeltaCheckRule.Direction.DECREASE
        self.rule.delta_type = DeltaCheckRule.DeltaType.ABSOLUTE
        self.rule.threshold = 0
        self.rule.save()
        earlier = make_order(self.patient, [self.test], when=timezone.now() - timedelta(days=1))
        self._result(earlier, 5.0)
        current = make_order(self.patient, [self.test])
        self.assertEqual(run_delta_checks(current, self.test, 5.0), [])

    def test_no_prior_result_produces_no_flag(self):
        current = make_order(self.patient, [self.test])
        self.assertEqual(run_delta_checks(current, self.test, 99.0), [])


class CriticalValueTests(TestCase):
    def setUp(self):
        self.test = make_test(reference_range={"min": 3.9, "max": 5.8, "panicLow": 2.2, "panicHigh": 25.0})
        self.patient = make_patient()
        self.order = make_order(self.patient, [self.test])

    def test_low_critical_raises_notification(self):
        notification = check_critical_value(self.order, self.test, 1.5, "tech")
        self.assertIsNotNone(notification)
        self.assertEqual(notification.critical_type, CriticalValueNotification.CriticalType.LOW)
        self.assertIn("2.2", notification.threshold)

    def test_high_critical_raises_notification(self):
        notification = check_critical_value(self.order, self.test, 30.0, "tech")
        self.assertEqual(notification.critical_type, CriticalValueNotification.CriticalType.HIGH)

    def test_in_range_value_raises_nothing(self):
        self.assertIsNone(check_critical_value(self.order, self.test, 5.0, "tech"))

    def test_duplicate_notification_is_not_raised(self):
        check_critical_value(self.order, self.test, 30.0, "tech")
        self.assertIsNone(check_critical_value(self.order, self.test, 31.0, "tech"))

    def test_stat_orders_get_a_shorter_escalation_window(self):
        stat_order = make_order(self.patient, [self.test], priority="STAT")
        notification = check_critical_value(stat_order, self.test, 30.0, "tech")
        window = (notification.escalation_due_at - notification.created_at).total_seconds() / 60
        self.assertAlmostEqual(window, 30, delta=1)

    def test_demographic_critical_limit_overrides_the_default(self):
        DemographicReferenceRange.objects.create(
            test=self.test, test_code=self.test.code, age_min=0, age_max=1,
            gender="All", low_critical=1.0, high_critical=8.0, created_at=timezone.now(),
        )
        infant = make_patient(mrn="MRN-INF", dob=timezone.localdate() - timedelta(days=200))
        infant_order = make_order(infant, [self.test])
        notification = check_critical_value(infant_order, self.test, 10.0, "tech")
        self.assertIsNotNone(notification)
        self.assertIn("8", notification.threshold)


class ReflexTests(TestCase):
    def setUp(self):
        self.trigger = make_test(code="TSH", name="TSH")
        self.reflexed = make_test(code="FT4", name="Free T4")
        self.patient = make_patient()
        self.order = make_order(self.patient, [self.trigger])
        self.rule = ReflexRule.objects.create(
            name="TSH high → FT4", trigger_test=self.trigger,
            operator=ReflexRule.Operator.GT, threshold=4.0,
            add_test=self.reflexed, add_test_code=self.reflexed.code,
        )

    def test_rule_adds_test_to_order(self):
        added = evaluate_reflex_rules(self.order, self.trigger, 8.0)
        self.assertEqual(added, [self.reflexed])
        self.assertTrue(self.order.tests.filter(pk=self.reflexed.pk).exists())

    def test_rule_does_not_fire_below_threshold(self):
        self.assertEqual(evaluate_reflex_rules(self.order, self.trigger, 2.0), [])

    def test_rule_fires_only_once_per_order(self):
        evaluate_reflex_rules(self.order, self.trigger, 8.0)
        self.assertEqual(evaluate_reflex_rules(self.order, self.trigger, 9.0), [])

    def test_disabled_rule_does_not_fire(self):
        self.rule.enabled = False
        self.rule.save()
        self.assertEqual(evaluate_reflex_rules(self.order, self.trigger, 8.0), [])


class DemographicRangeTests(TestCase):
    def setUp(self):
        self.test = make_test()
        common = {"test": self.test, "test_code": self.test.code, "created_at": timezone.now()}
        self.adult = DemographicReferenceRange.objects.create(
            gender="All", low_normal=3.9, high_normal=5.8, **common
        )
        self.female = DemographicReferenceRange.objects.create(
            gender="F", low_normal=3.5, high_normal=5.5, **common
        )
        self.paediatric = DemographicReferenceRange.objects.create(
            age_min=0, age_max=12, gender="All", low_normal=3.0, high_normal=5.0, **common
        )

    def test_most_specific_match_wins(self):
        child = make_patient(mrn="P-CHILD", dob=timezone.localdate() - timedelta(days=365 * 8), gender="F")
        chosen = find_reference_range(self.test, child)
        self.assertIn(chosen, {self.paediatric, self.female})
        self.assertGreaterEqual(chosen.specificity, 2)

    def test_sex_specific_range_used_for_matching_patient(self):
        adult = make_patient(mrn="P-F", dob=date(1980, 1, 1), gender="F")
        self.assertEqual(find_reference_range(self.test, adult), self.female)

    def test_sex_specific_range_not_applied_to_other_sex(self):
        male = make_patient(mrn="P-M", dob=date(1980, 1, 1), gender="M")
        self.assertEqual(find_reference_range(self.test, male), self.adult)

    def test_age_scoped_range_is_skipped_when_age_is_unknown(self):
        """Regression: the original applied age-scoped intervals to patients
        whose age was unknown."""
        self.assertFalse(
            self.paediatric.applies_to(age_years=None, gender="F")
        )

    def test_pregnancy_range_not_used_for_non_pregnant_patient(self):
        pregnancy = DemographicReferenceRange.objects.create(
            test=self.test, test_code=self.test.code, gender="F", pregnancy=True,
            low_normal=3.0, high_normal=5.0, created_at=timezone.now(),
        )
        self.assertFalse(pregnancy.applies_to(age_years=30, gender="F", is_pregnant=False))
        self.assertTrue(pregnancy.applies_to(age_years=30, gender="F", is_pregnant=True))


class CalculatedTestTests(TestCase):
    def test_ldl_friedewald(self):
        value = compute_calculated_test(
            CalculatedTest.Formula.LDL_FRIEDEWALD, {"TC": 6.0, "HDL": 1.2, "TG": 2.2}
        )
        self.assertAlmostEqual(value, 3.8, places=1)

    def test_ldl_invalid_above_triglyceride_limit(self):
        self.assertIsNone(compute_calculated_test(
            CalculatedTest.Formula.LDL_FRIEDEWALD, {"TC": 6.0, "HDL": 1.2, "TG": 5.0}
        ))

    def test_missing_input_returns_none(self):
        self.assertIsNone(compute_calculated_test(
            CalculatedTest.Formula.LDL_FRIEDEWALD, {"TC": 6.0, "HDL": 1.2}
        ))

    def test_anion_gap(self):
        self.assertAlmostEqual(
            compute_calculated_test(CalculatedTest.Formula.ANION_GAP,
                                    {"Na": 140, "Cl": 102, "HCO3": 24}), 14.0
        )

    def test_ag_ratio_rejects_non_positive_globulin(self):
        self.assertIsNone(compute_calculated_test(
            CalculatedTest.Formula.AG_RATIO, {"ALB": 45, "TP": 45}
        ))

    def test_egfr_ckd_epi_female(self):
        value = compute_calculated_test(
            CalculatedTest.Formula.EGFR_CKD_EPI, {"CREA": 70},
            patient_age=50, patient_gender="F",
        )
        self.assertTrue(85 <= value <= 100, f"eGFR out of expected band: {value}")

    def test_egfr_requires_demographics(self):
        self.assertIsNone(compute_calculated_test(
            CalculatedTest.Formula.EGFR_CKD_EPI, {"CREA": 70}
        ))

    def test_corrected_calcium(self):
        self.assertAlmostEqual(
            compute_calculated_test(CalculatedTest.Formula.CORRECTED_CALCIUM,
                                    {"CA": 2.20, "ALB": 30}), 2.40, places=2
        )

    def test_unknown_formula_returns_none(self):
        self.assertIsNone(compute_calculated_test("not_a_formula", {"X": 1}))


class NotifiableConditionTests(TestCase):
    def test_all_matching_conditions_are_raised(self):
        """Regression: the original returned after the first match."""
        test = make_test(code="CULT", name="Culture")
        patient = make_patient()
        order = make_order(patient, [test])
        for name in ("Salmonellosis", "Notifiable enteric pathogen"):
            condition = NotifiableCondition.objects.create(
                name=name, reporting_body="Public Health", created_at=timezone.now()
            )
            condition.tests.add(test)

        raised = check_notifiable_conditions(order, test)
        self.assertEqual(len(raised), 2)

    def test_duplicate_notification_is_not_raised(self):
        test = make_test(code="CULT2")
        patient = make_patient()
        order = make_order(patient, [test])
        condition = NotifiableCondition.objects.create(
            name="Cholera", reporting_body="Public Health", created_at=timezone.now()
        )
        condition.tests.add(test)
        check_notifiable_conditions(order, test)
        self.assertEqual(check_notifiable_conditions(order, test), [])
