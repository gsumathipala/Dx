"""Evaluating rules against a result.

The engine has three parts: gathering the facts, testing the conditions, and
applying the actions. Keeping them separate matters more than it looks —
``build_facts`` is what gets stored on every execution, so a rule's behaviour
can be re-derived later from exactly what it saw, and the condition evaluator
is a pure function over a plain dictionary and can be tested without touching
the database.

Facts are gathered once per result and shared by every rule evaluated against
it, so a hundred rules cost one set of queries rather than a hundred.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.rules.models import Rule, RuleAction, RuleCondition, RuleExecution

logger = logging.getLogger("dx.rules")

Subject = RuleCondition.Subject
Operator = RuleCondition.Operator


# ── Facts ────────────────────────────────────────────────────────────────────


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reference_position(test, result, patient) -> str:
    """Where a result sits relative to its reference interval.

    Demographic intervals win over the catalogue default, matching what the
    clinical engine does, so a rule written as "within reference interval"
    means the same thing on a neonate as on an adult.
    """
    from apps.clinical.services import find_reference_range

    numeric = result.numeric_value if result is not None else None
    if numeric is None or test is None:
        return "unknown"

    low = high = None
    demographic = find_reference_range(test, patient)
    if demographic is not None:
        low, high = demographic.low_normal, demographic.high_normal
    if low is None:
        low = test.normal_low
    if high is None:
        high = test.normal_high

    if low is None and high is None:
        return "unknown"
    if low is not None and numeric < low:
        return "below"
    if high is not None and numeric > high:
        return "above"
    return "within"


def build_facts(order, test, result, *, entered_by: str = "") -> dict:
    """Every fact a condition may refer to, for one result on one order."""
    from apps.clinical.models import DeltaCheckFlag
    from apps.compliance.services import check_qc_status
    from apps.laboratory.models import Result

    patient = order.patient
    numeric = result.numeric_value if result is not None else None
    flags = list(result.result_flags or []) if result is not None else []

    # The most recent earlier numeric result for this test on this patient.
    prior_value = prior_age_days = None
    if test is not None:
        previous = (
            Result.objects.filter(
                order__patient_id=order.patient_id,
                test=test,
                numeric_value__isnull=False,
                order__timestamp__lt=order.timestamp,
            )
            .exclude(order_id=order.pk)
            .select_related("order")
            .order_by("-order__timestamp")
            .first()
        )
        if previous is not None:
            prior_value = previous.numeric_value
            prior_age_days = (order.timestamp - previous.order.timestamp).days

    delta_percent = delta_absolute = None
    if numeric is not None and prior_value is not None:
        delta_absolute = abs(numeric - prior_value)
        if prior_value:
            delta_percent = abs((numeric - prior_value) / prior_value) * 100

    has_delta = False
    if test is not None:
        has_delta = DeltaCheckFlag.objects.filter(order=order, test=test).exists()

    specimen = order.specimens.first()
    receipt = order.receipts.order_by("-received_at").first()

    qc = check_qc_status(test) if test is not None else None
    qc_status = (
        "not-required" if qc is None
        else ("in-control" if qc.allowed else "out-of-control")
    )

    diagnoses = []
    if hasattr(order, "diagnoses"):
        diagnoses = [d.code_value for d in order.diagnoses.all()]

    source = "instrument" if (entered_by or "").startswith("instrument:") else "manual"

    return {
        Subject.RESULT_VALUE: numeric,
        Subject.RESULT_TEXT: (result.value if result is not None else "") or "",
        Subject.RESULT_FLAG: flags[0] if flags else "Normal",
        Subject.RESULT_POSITION: _reference_position(test, result, patient),
        Subject.RESULT_IS_CRITICAL: any("Critical" in flag for flag in flags),
        Subject.RESULT_HAS_DELTA: has_delta,
        Subject.TEST_CODE: test.code if test is not None else "",
        Subject.TEST_DEPARTMENT: (
            test.department.name if test is not None and test.department_id else ""
        ),
        Subject.PATIENT_AGE_YEARS: patient.age if patient else None,
        Subject.PATIENT_AGE_DAYS: (
            (timezone.localdate() - patient.dob).days if patient and patient.dob else None
        ),
        Subject.PATIENT_SEX: (patient.gender if patient else "") or "",
        Subject.ORDER_PRIORITY: order.priority or "",
        Subject.ORDER_ICD10: diagnoses,
        Subject.SPECIMEN_TYPE: (specimen.type if specimen else "") or "",
        Subject.SPECIMEN_CONDITION: (receipt.condition if receipt else "") or "",
        Subject.PRIOR_VALUE: prior_value,
        Subject.PRIOR_AGE_DAYS: prior_age_days,
        Subject.DELTA_PERCENT: delta_percent,
        Subject.DELTA_ABSOLUTE: delta_absolute,
        Subject.QC_STATUS: qc_status,
        Subject.ENTERED_BY_SOURCE: source,
    }


# ── Condition evaluation ─────────────────────────────────────────────────────


def _split_list(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def evaluate_condition(condition: RuleCondition, facts: dict) -> bool:
    """Test one condition against the gathered facts.

    A fact that is unavailable (no previous result, unknown date of birth)
    makes every comparison false except ``is blank``. That is deliberate: a
    rule must not fire because something could not be measured. Silence is not
    evidence of normality.
    """
    fact = facts.get(condition.subject)
    operator = condition.operator

    if operator == Operator.BLANK:
        return fact in (None, "", [], {})
    if operator == Operator.NOT_BLANK:
        return fact not in (None, "", [], {})

    if fact is None:
        return False

    # A list-valued fact (ICD-10 codes) is a membership test, not a comparison.
    if isinstance(fact, list):
        wanted = _split_list(condition.value) or [condition.value.strip()]
        overlap = any(item in fact for item in wanted if item)
        if operator in (Operator.IN, Operator.EQ, Operator.CONTAINS):
            return overlap
        if operator in (Operator.NOT_IN, Operator.NE):
            return not overlap
        return False

    if condition.subject in RuleCondition.BOOLEAN_SUBJECTS:
        wanted = str(condition.value).strip().lower() in {"1", "true", "yes", "on"}
        return bool(fact) == wanted if operator == Operator.EQ else bool(fact) != wanted

    if condition.subject in RuleCondition.NUMERIC_SUBJECTS:
        left = _as_float(fact)
        if left is None:
            return False
        if operator == Operator.BETWEEN:
            low, high = _as_float(condition.value), _as_float(condition.value_to)
            if low is None or high is None:
                return False
            return low <= left <= high
        if operator in (Operator.IN, Operator.NOT_IN):
            members = [_as_float(item) for item in _split_list(condition.value)]
            present = left in [m for m in members if m is not None]
            return present if operator == Operator.IN else not present
        right = _as_float(condition.value)
        if right is None:
            return False
        return {
            Operator.EQ: left == right,
            Operator.NE: left != right,
            Operator.LT: left < right,
            Operator.LTE: left <= right,
            Operator.GT: left > right,
            Operator.GTE: left >= right,
        }.get(operator, False)

    # Everything else is compared as case-insensitive text.
    left = str(fact).strip().lower()
    right = str(condition.value).strip().lower()
    if operator == Operator.EQ:
        return left == right
    if operator == Operator.NE:
        return left != right
    if operator == Operator.CONTAINS:
        return right in left
    if operator in (Operator.IN, Operator.NOT_IN):
        members = [item.lower() for item in _split_list(condition.value)]
        return (left in members) if operator == Operator.IN else (left not in members)
    return False


def matches(rule: Rule, facts: dict, conditions=None) -> bool:
    """Whether a rule's conditions hold: AND within a group, OR across groups.

    A rule with no conditions matches everything. That is a legitimate thing to
    want (append a standard footnote to every microbiology report) but it is
    also the easiest way to write a rule by accident, so the builder warns.
    """
    conditions = list(rule.conditions.all() if conditions is None else conditions)
    if not conditions:
        return True

    groups: dict[int, list[RuleCondition]] = {}
    for condition in conditions:
        groups.setdefault(condition.group, []).append(condition)

    return any(
        all(evaluate_condition(condition, facts) for condition in group)
        for group in groups.values()
    )


# ── Applying actions ─────────────────────────────────────────────────────────


COMMENT_MARK = "—"  # em dash separating appended rule comments


def _append_comment(result, text: str, rule: Rule) -> bool:
    """Add an interpretive comment, without duplicating it on re-entry.

    Comments are attributed inline so a reader can tell an automatic note from
    something a scientist wrote. CAP requires interpretive comments to be
    identifiable as such; an unattributed sentence in the comment field reads
    as a human opinion, which it is not.
    """
    stamped = f"[{rule.name}] {text}"
    existing = result.comments or ""
    if stamped in existing:
        return False
    result.comments = f"{existing}\n{stamped}".strip() if existing else stamped
    result.save(update_fields=["comments"])
    return True


def _set_flag(result, flag: str) -> bool:
    flags = list(result.result_flags or [])
    if flag in flags:
        return False
    flags.append(flag)
    result.result_flags = flags
    result.save(update_fields=["result_flags"])
    return True


def _add_test(order, test) -> bool:
    if test is None or order.tests.filter(pk=test.pk).exists():
        return False
    order.tests.add(test)
    order.updated_at = timezone.now()
    order.save(update_fields=["updated_at"])
    return True


def _notify(rule: Rule, action: RuleAction, order, test) -> bool:
    """Send an internal message to everyone holding a role.

    The message has no human sender — ``sender_label`` carries the rule
    instead. Attributing an automatic message to whoever happened to enter the
    result would be a small lie that becomes a large one during an
    investigation.
    """
    from apps.accounts.models import User
    from apps.operations.models import Message

    body = (action.text or rule.description or rule.summary())[:4000]
    recipients = list(
        User.objects.filter(role=action.recipient_role, is_active=True)
    ) if action.recipient_role else [None]

    for recipient in recipients:
        Message.objects.create(
            sender=None,
            sender_label=f"rule:{rule.name}",
            recipient=recipient,
            subject=f"Rule fired: {rule.name}"[:255],
            body=body,
            related_entity_type="laboratory.Order",
            related_entity_id=str(order.pk),
        )
    return bool(recipients)


def _raise_exception(rule: Rule, action: RuleAction, order, test) -> bool:
    from apps.operations.exceptions import ExceptionSource, raise_exception

    raise_exception(
        source=ExceptionSource.RULE,
        source_key=f"rule:{rule.pk}:{order.pk}:{test.code if test else '-'}",
        title=f"{rule.name}",
        detail=action.text or rule.summary(),
        severity=action.severity or "medium",
        order=order,
        test_code=test.code if test is not None else "",
    )
    return True


def _hold(result) -> bool:
    """Prevent a result being released until a human has looked at it."""
    from apps.common.constants import OrderStatus

    if result.status == OrderStatus.RESULTED:
        return False
    result.status = OrderStatus.RESULTED
    result.clinical_verified_by = None
    result.save(update_fields=["status", "clinical_verified_by"])
    return True


def apply_actions(rule: Rule, order, test, result, actions) -> tuple[list[str], bool]:
    """Run a matched rule's actions. Returns (applied labels, auto-verify asked)."""
    applied: list[str] = []
    wants_auto_verify = False

    for action in actions:
        try:
            if action.kind == RuleAction.Kind.APPEND_COMMENT and result is not None:
                if _append_comment(result, action.text or "", rule):
                    applied.append(action.describe())
            elif action.kind == RuleAction.Kind.SET_FLAG and result is not None:
                if _set_flag(result, action.flag):
                    applied.append(action.describe())
            elif action.kind == RuleAction.Kind.ADD_TEST:
                if _add_test(order, action.add_test):
                    applied.append(action.describe())
            elif action.kind == RuleAction.Kind.NOTIFY:
                if _notify(rule, action, order, test):
                    applied.append(action.describe())
            elif action.kind == RuleAction.Kind.RAISE_EXCEPTION:
                if _raise_exception(rule, action, order, test):
                    applied.append(action.describe())
            elif action.kind == RuleAction.Kind.HOLD and result is not None:
                if _hold(result):
                    applied.append(action.describe())
            elif action.kind == RuleAction.Kind.AUTO_VERIFY:
                # Never applied here. Auto-verification runs after the order
                # has settled, behind its own guardrails — see autoverify.py.
                wants_auto_verify = True
        except Exception:
            # A broken rule must never lose a result. The failure is logged and
            # surfaced on the execution record rather than raised.
            logger.exception("Rule %s action %s failed", rule.name, action.kind)

    return applied, wants_auto_verify


# ── Entry point ──────────────────────────────────────────────────────────────


def applicable_rules(trigger: str, test) -> list[Rule]:
    """Live rules for this trigger and test, in evaluation order."""
    queryset = (
        Rule.objects.filter(trigger=trigger, active=True)
        .prefetch_related("conditions", "actions", "actions__add_test")
        .order_by("priority", "name")
    )
    if test is not None:
        queryset = queryset.filter(test__isnull=True) | queryset.filter(test=test)
    else:
        queryset = queryset.filter(test__isnull=True)
    return [rule for rule in queryset.distinct() if rule.is_approved]


def run_for_result(order, test, result, *, trigger: str, entered_by: str = "") -> dict:
    """Evaluate every applicable rule against one result.

    Returns ``{"executions": [...], "auto_verify_requested": bool, "facts": {}}``.
    The caller decides what to do about auto-verification; this function never
    releases anything.
    """
    rules = applicable_rules(trigger, test)
    if not rules:
        return {"executions": [], "auto_verify_requested": False, "facts": {}}

    facts = build_facts(order, test, result, entered_by=entered_by)
    executions: list[RuleExecution] = []
    auto_verify_requested = False

    for rule in rules:
        if not matches(rule, facts):
            continue

        applied, wants_auto_verify = apply_actions(
            rule, order, test, result, list(rule.actions.all())
        )
        auto_verify_requested = auto_verify_requested or wants_auto_verify

        executions.append(RuleExecution.objects.create(
            rule=rule,
            rule_name=rule.name,
            rule_version=rule.version,
            order=order,
            result=result,
            test_code=test.code if test is not None else "",
            facts=_serialisable(facts),
            actions_applied=applied,
            outcome=RuleExecution.Outcome.APPLIED if applied or wants_auto_verify
            else RuleExecution.Outcome.BLOCKED,
        ))

        if rule.stop_on_match:
            break

    return {
        "executions": executions,
        "auto_verify_requested": auto_verify_requested,
        "facts": facts,
    }


def _serialisable(facts: dict) -> dict:
    """Facts as plain JSON. Keys are already strings via TextChoices."""
    return {str(key): value for key, value in facts.items()}


def simulate(rule: Rule, facts: dict) -> dict:
    """Evaluate a rule against supplied facts without applying anything.

    Used by the builder's 'test this rule' panel, so a rule can be checked
    against a real historic result before it is approved — which is the
    difference between validating a rule and hoping.
    """
    per_condition = [
        {
            "description": condition.describe(),
            "group": condition.group,
            "fact": facts.get(condition.subject),
            "holds": evaluate_condition(condition, facts),
        }
        for condition in rule.conditions.all()
    ]
    return {
        "matches": matches(rule, facts),
        "conditions": per_condition,
        "actions": [action.describe() for action in rule.actions.all()],
    }
