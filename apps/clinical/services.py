"""The clinical decision engine.

Ported from ``src/lib/clinical-engine.ts``, with the defects found in the
original corrected — each is noted at the point it mattered.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.clinical.models import (
    CalculatedTest,
    CriticalValueNotification,
    DeltaCheckFlag,
    DeltaCheckRule,
    DemographicReferenceRange,
    EpidemiologyNotification,
    NotifiableCondition,
    ReflexActivation,
    ReflexRule,
)

logger = logging.getLogger("dx.clinical")


# ── Delta checks ─────────────────────────────────────────────────────────────


def run_delta_checks(order, test, current_value: float) -> list[DeltaCheckFlag]:
    """Compare a result against the patient's previous value for the same test.

    Two corrections against the original: the previous result is now required
    to be genuinely *earlier* than the current order (the TypeScript version
    took the five most recent orders regardless of direction, so a result could
    be compared against a later one), and the lookback is bounded by the rule's
    own window rather than an arbitrary five orders.
    """
    flags: list[DeltaCheckFlag] = []
    rules = DeltaCheckRule.objects.filter(test=test, enabled=True)
    if not rules.exists():
        return flags

    from apps.laboratory.models import Result

    for rule in rules:
        cutoff = order.timestamp - timedelta(days=rule.lookback_days)
        previous = (
            Result.objects.filter(
                order__patient_id=order.patient_id,
                test=test,
                numeric_value__isnull=False,
                order__timestamp__lt=order.timestamp,
                order__timestamp__gte=cutoff,
            )
            .exclude(order_id=order.pk)
            .select_related("order")
            .order_by("-order__timestamp")
            .first()
        )
        if previous is None:
            continue

        previous_value = previous.numeric_value
        delta_absolute = abs(current_value - previous_value)
        delta_percent = (
            abs((current_value - previous_value) / previous_value) * 100
            if previous_value
            else None
        )

        # An unchanged value is neither an increase nor a decrease. The original
        # classified equality as 'decrease', which fired decrease-only rules on
        # identical results.
        if current_value > previous_value:
            direction = DeltaCheckRule.Direction.INCREASE
        elif current_value < previous_value:
            direction = DeltaCheckRule.Direction.DECREASE
        else:
            direction = None

        if rule.direction != DeltaCheckRule.Direction.ANY and direction != rule.direction:
            continue

        if rule.delta_type == DeltaCheckRule.DeltaType.PERCENT:
            exceeded = delta_percent is not None and delta_percent >= rule.threshold
        else:
            exceeded = delta_absolute >= rule.threshold

        if not exceeded:
            continue

        flags.append(
            DeltaCheckFlag.objects.create(
                order=order,
                test=test,
                rule=rule,
                previous_order=previous.order,
                previous_value=previous_value,
                previous_timestamp=previous.order.timestamp,
                current_value=current_value,
                delta_percent=delta_percent,
                delta_absolute=delta_absolute,
            )
        )

    return flags


# ── Critical values ──────────────────────────────────────────────────────────


def check_critical_value(order, test, value: float, entered_by: str) -> CriticalValueNotification | None:
    """Raise a notification when a result falls outside the panic limits.

    Demographic-specific critical limits take precedence over the test's
    default range, since a paediatric panic value differs from an adult one.
    """
    patient = order.patient
    demographic = find_reference_range(test, patient)

    critical_low = critical_high = None
    if demographic is not None:
        critical_low, critical_high = demographic.low_critical, demographic.high_critical
    if critical_low is None:
        critical_low = test.panic_low
    if critical_high is None:
        critical_high = test.panic_high

    units = test.units or ""
    if critical_low is not None and value < critical_low:
        critical_type = CriticalValueNotification.CriticalType.LOW
        threshold = f"< {critical_low:g} {units}".strip()
    elif critical_high is not None and value > critical_high:
        critical_type = CriticalValueNotification.CriticalType.HIGH
        threshold = f"> {critical_high:g} {units}".strip()
    else:
        return None

    escalation_minutes = 30 if order.priority == "STAT" else 60
    notification, created = CriticalValueNotification.objects.get_or_create(
        order=order,
        test=test,
        status=CriticalValueNotification.Status.PENDING,
        defaults={
            "patient": patient,
            "test_code": test.code,
            "value": str(value),
            "threshold": threshold,
            "critical_type": critical_type,
            "created_by": entered_by,
            "escalation_due_at": timezone.now() + timedelta(minutes=escalation_minutes),
        },
    )
    return notification if created else None


# ── Reflex testing ───────────────────────────────────────────────────────────


@transaction.atomic
def evaluate_reflex_rules(order, test, value: float) -> list:
    """Add follow-on tests triggered by a result."""
    added = []
    rules = ReflexRule.objects.filter(trigger_test=test, enabled=True).select_related("add_test")

    for rule in rules:
        if not rule.matches(value):
            continue
        activation, created = ReflexActivation.objects.get_or_create(
            order=order,
            rule=rule,
            defaults={
                "trigger_value": str(value),
                "new_test": rule.add_test,
            },
        )
        if not created:
            continue

        if not order.tests.filter(pk=rule.add_test_id).exists():
            order.tests.add(rule.add_test)
            order.updated_at = timezone.now()
            order.save(update_fields=["updated_at"])
        added.append(rule.add_test)

    return added


# ── Notifiable conditions ────────────────────────────────────────────────────


def check_notifiable_conditions(order, test) -> list[EpidemiologyNotification]:
    """Flag results that must be reported to public health.

    The original returned after the first match; a specimen can satisfy more
    than one notifiable condition, so all matches are now raised.
    """
    raised = []
    conditions = NotifiableCondition.objects.filter(active=True, tests=test)

    for condition in conditions:
        notification, created = EpidemiologyNotification.objects.get_or_create(
            order=order,
            condition=condition,
            defaults={"patient": order.patient},
        )
        if created:
            raised.append(notification)

    return raised


# ── Demographic reference intervals ──────────────────────────────────────────


def find_reference_range(test, patient, *, is_pregnant: bool = False, trimester: int | None = None):
    """Pick the most specific reference interval valid for this patient.

    Unlike the original scoring loop, an interval scoped to an age band or a
    sex is skipped outright when that demographic is unknown, rather than
    silently matching.
    """
    age = patient.age if patient else None
    gender = patient.gender if patient else None

    candidates = [
        candidate
        for candidate in DemographicReferenceRange.objects.filter(test=test, active=True)
        if candidate.applies_to(
            age_years=age, gender=gender, is_pregnant=is_pregnant, trimester=trimester
        )
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate.specificity)


# ── Calculated tests ─────────────────────────────────────────────────────────


def compute_calculated_test(
    formula: str,
    inputs: dict[str, float],
    *,
    patient_age: int | None = None,
    patient_gender: str | None = None,
) -> float | None:
    """Evaluate a derived analyte. Returns None when inputs are missing or the
    formula is not valid for the supplied values."""

    def need(*codes: str):
        values = []
        for code in codes:
            value = inputs.get(code)
            if value is None:
                return None
            values.append(float(value))
        return values

    if formula == CalculatedTest.Formula.LDL_FRIEDEWALD:
        values = need("TC", "HDL", "TG")
        if values is None:
            return None
        total, hdl, triglycerides = values
        # Friedewald is invalid above 4.5 mmol/L triglycerides.
        if triglycerides > 4.5:
            return None
        return round(total - hdl - triglycerides / 2.2, 2)

    if formula == CalculatedTest.Formula.ANION_GAP:
        values = need("Na", "Cl", "HCO3")
        if values is None:
            return None
        sodium, chloride, bicarbonate = values
        return round(sodium - (chloride + bicarbonate), 1)

    if formula == CalculatedTest.Formula.AG_RATIO:
        values = need("ALB", "TP")
        if values is None:
            return None
        albumin, total_protein = values
        globulin = total_protein - albumin
        if globulin <= 0:
            return None
        return round(albumin / globulin, 2)

    if formula == CalculatedTest.Formula.EGFR_CKD_EPI:
        values = need("CREA")
        if values is None or patient_age is None or patient_gender is None:
            return None
        (creatinine_umol,) = values
        creatinine_mgdl = creatinine_umol / 88.4
        is_female = patient_gender == "F"
        kappa = 0.7 if is_female else 0.9
        alpha = -0.241 if is_female else -0.302
        sex_factor = 1.012 if is_female else 1.0
        ratio = creatinine_mgdl / kappa
        egfr = (
            142
            * min(ratio, 1) ** alpha
            * max(ratio, 1) ** -1.200
            * (0.9938**patient_age)
            * sex_factor
        )
        return round(egfr)

    if formula == CalculatedTest.Formula.CORRECTED_CALCIUM:
        values = need("CA", "ALB")
        if values is None:
            return None
        calcium, albumin = values
        # Payne's formula, albumin in g/L, calcium in mmol/L.
        return round(calcium + 0.02 * (40 - albumin), 2)

    if formula == CalculatedTest.Formula.OSMOLALITY:
        values = need("Na", "UREA", "GLU")
        if values is None:
            return None
        sodium, urea, glucose = values
        return round(2 * sodium + urea + glucose, 1)

    if formula == CalculatedTest.Formula.TRANSFERRIN_SATURATION:
        values = need("FE", "TIBC")
        if values is None:
            return None
        iron, tibc = values
        if tibc <= 0:
            return None
        return round(iron / tibc * 100, 1)

    return None


def run_clinical_engine(order, test, result, entered_by: str) -> dict:
    """Run every rule that applies to a newly entered result.

    Unlike the original, which fired these as un-awaited promises whose failures
    only reached the console, each rule runs inside the caller's transaction and
    failures are collected and returned so the UI can surface them.
    """
    outcome = {"delta_flags": [], "critical": None, "reflex_added": [], "notifiable": [], "errors": []}

    if result.numeric_value is not None:
        for label, call in (
            ("delta", lambda: outcome.__setitem__("delta_flags", run_delta_checks(order, test, result.numeric_value))),
            ("critical", lambda: outcome.__setitem__("critical", check_critical_value(order, test, result.numeric_value, entered_by))),
            ("reflex", lambda: outcome.__setitem__("reflex_added", evaluate_reflex_rules(order, test, result.numeric_value))),
        ):
            try:
                call()
            except Exception as exc:  # a rule failure must not lose the result
                logger.exception("Clinical engine %s check failed", label)
                outcome["errors"].append(f"{label}: {exc}")

    try:
        outcome["notifiable"] = check_notifiable_conditions(order, test)
    except Exception as exc:
        logger.exception("Notifiable condition check failed")
        outcome["errors"].append(f"notifiable: {exc}")

    return outcome
