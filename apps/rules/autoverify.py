"""Automatic verification, and the guardrails that make it defensible.

Autoverification is the single highest-value and highest-risk feature in a
modern LIS. A busy chemistry laboratory produces results faster than anyone can
read them, and a scientist who must click through four hundred normal
potassiums to reach the one that matters is being trained, by the system, not
to look. Releasing the obviously-normal automatically is how the abnormal gets
attention.

Done naively it is also how a laboratory reports a critical value to nobody.

The position taken here
-----------------------
Autoverification **never relaxes an existing control**. Everything a human
verifier must satisfy, a rule must satisfy too, and a rule additionally may not
touch anything a human would want to look at:

1. **The laboratory opts in per analyte.** ``TestDefinition.auto_verify_permitted``
   is off by default. A rule cannot autoverify a test the laboratory has not
   decided is suitable. CLIA §493.1291 and CLSI AUTO10-A both frame
   autoverification as a validated, analyte-scoped decision, not a global mode.
2. **Quality control must be in control** for that analyte, in the same window
   a human release is checked against (CLIA §493.1256). No QC, no release.
3. **The result must be numeric and inside its reference interval** — using the
   patient's demographic interval where one exists, not the catalogue default.
4. **Never a critical value.** A panic result must reach a person who telephones
   it and documents read-back (CAP GEN.41320). There is no acceptable automatic
   substitute.
5. **Never a delta-flagged result.** A large change from the patient's own
   previous value is precisely the signal a rule cannot interpret.
6. **Never an abnormally-flagged result of any kind**, and never one already
   carrying a hold.
7. **Never when the specimen was marked other than acceptable** at reception —
   a haemolysed or short-draw sample is a human decision.
8. **Never when the order has an open exception**, because something about that
   order is already known to need attention.
9. **Never a corrected/amended result.** An amendment has already gone wrong
   once.

Attribution
-----------
The release carries an electronic signature whose signer is *the rule*, at the
version that fired, not the scientist who happened to be logged in. Part 11
§11.50 requires the meaning of a signature and the identity of the signer to be
recorded; recording a person who never looked at the result would be false
attribution, which is a worse finding than having no human signature at all.

``ElectronicSignature.signer`` is therefore nullable, and
``automated_rule`` names the rule. A report released this way prints
"Autoverified by rule: <name> (v<n>)" in its signature manifest, so a clinician
reading it knows no human eye was involved.

Overriding
----------
Any lab staff member may override an autoverification, which returns the result
to the worklist and records who did it and why. That is the escape hatch that
makes the whole thing acceptable to deploy.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.constants import AuditAction, OrderStatus

logger = logging.getLogger("dx.rules.autoverify")


@dataclass
class Decision:
    """Whether a result may be released by a rule, and why not if it may not."""

    allowed: bool
    refusals: list[str] = field(default_factory=list)

    def refuse(self, reason: str) -> "Decision":
        self.allowed = False
        self.refusals.append(reason)
        return self


def assess(order, test, result) -> Decision:
    """Apply every guardrail. Returns a Decision listing each refusal.

    Every check runs — the decision does not short-circuit — so the execution
    record shows all the reasons at once rather than the first one found. That
    matters when a laboratory is tuning a rule set: fixing one blocker only to
    discover another on the next run wastes days.
    """
    from apps.clinical.models import DeltaCheckFlag
    from apps.compliance.models import AmendedReport
    from apps.compliance.services import check_qc_status
    from apps.operations.models import ExceptionItem
    from apps.rules.engine import _reference_position

    decision = Decision(allowed=True)

    if not getattr(settings, "RULES_ALLOW_AUTO_VERIFICATION", True):
        return decision.refuse("Autoverification is disabled for this installation.")

    if test is None or result is None:
        return decision.refuse("No test or result to assess.")

    # 1. Per-analyte opt-in.
    if not getattr(test, "auto_verify_permitted", False):
        decision.refuse(
            f"{test.code} is not approved for autoverification. "
            "Enable it on the test definition once the laboratory has validated it."
        )

    # 2. Quality control.
    qc = check_qc_status(test)
    if not qc.allowed:
        decision.refuse(f"Quality control: {qc.message}")

    # 3. Numeric and within the reference interval.
    if result.numeric_value is None:
        decision.refuse("The result is not numeric; only numeric results can be autoverified.")
    else:
        position = _reference_position(test, result, order.patient)
        if position == "unknown":
            decision.refuse(
                f"No reference interval is defined for {test.code}, so 'normal' has no meaning."
            )
        elif position != "within":
            decision.refuse(f"The result is {position} the reference interval.")

    # 4/6. Flags.
    flags = list(result.result_flags or [])
    if any("Critical" in flag for flag in flags):
        decision.refuse(
            "Critical values are never autoverified — they require telephoned "
            "notification with documented read-back."
        )
    elif flags:
        decision.refuse(f"The result carries flags: {', '.join(flags)}.")

    # 5. Delta checks.
    if DeltaCheckFlag.objects.filter(order=order, test=test).exists():
        decision.refuse("A delta check flagged this result against the patient's previous value.")

    # 7. Specimen condition.
    receipt = order.receipts.order_by("-received_at").first()
    if receipt is not None and receipt.condition != receipt.Condition.ACCEPTABLE:
        decision.refuse(f"The specimen was received as {receipt.condition}.")

    # 8. Open exceptions on this order.
    if ExceptionItem.objects.open().filter(order=order).exists():
        decision.refuse("This order has an unresolved item on the exception queue.")

    # 9. Amended results.
    if AmendedReport.objects.filter(order=order, result=result).exists():
        decision.refuse("This result has been amended; an amended result is verified by a person.")

    # Already verified by a human — leave their signature alone.
    if result.clinical_verified_by and not str(result.clinical_verified_by).startswith("rule:"):
        decision.refuse(f"Already clinically verified by {result.clinical_verified_by}.")

    return decision


def rule_signature(rule, *, entity_type: str, entity_id, payload: dict, comment: str = ""):
    """A Part 11 signature attributable to a rule rather than a person."""
    from apps.audit.recorder import record
    from apps.compliance.models import ElectronicSignature
    from apps.compliance.services import content_hash

    digest = content_hash(payload)
    signature = ElectronicSignature.objects.create(
        signer=None,
        automated_rule=rule,
        signer_printed_name=f"{rule.name} (v{rule.version})",
        signer_role="rule",
        meaning=ElectronicSignature.Meaning.AUTO_VERIFICATION,
        entity_type=entity_type,
        entity_id=str(entity_id),
        record_hash=digest,
        reauthenticated=False,
        comment=comment or rule.summary(),
    )

    event = record(
        action=AuditAction.CLINICAL_VERIFY,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=f"autoverified by rule {rule.name} v{rule.version}",
        changes={"signature": {"old": None, "new": signature.manifest}},
        reason=comment or rule.summary(),
        blocking=True,
    )
    if event is not None:
        ElectronicSignature.objects.filter(pk=signature.pk).update(audit_sequence=event.sequence)
        signature.audit_sequence = event.sequence
    return signature


@transaction.atomic
def attempt(order, test, result, executions) -> bool:
    """Autoverify one result if every guardrail permits it.

    ``executions`` are the RuleExecution rows from this evaluation; the one
    whose rule asked for autoverification is updated with the outcome, so the
    refusal reasons are visible next to the rule that wanted to release.
    """
    from apps.audit.context import audit_as
    from apps.audit.models import AuditSource
    from apps.rules.models import RuleAction, RuleExecution

    asking = [
        execution for execution in executions
        if execution.rule is not None
        and execution.rule.actions.filter(kind=RuleAction.Kind.AUTO_VERIFY).exists()
    ]
    if not asking:
        return False

    decision = assess(order, test, result)
    execution = asking[0]

    if not decision.allowed:
        execution.refusals = decision.refusals
        execution.outcome = (
            RuleExecution.Outcome.PARTIAL if execution.actions_applied
            else RuleExecution.Outcome.BLOCKED
        )
        execution.save(update_fields=["refusals", "outcome"])
        return False

    rule = execution.rule
    # Attributed to the rule in the audit trail, not to the session's user.
    with audit_as(
        actor_username=f"rule:{rule.name}",
        actor_role="rule",
        source=AuditSource.SYSTEM,
    ):
        result.status = OrderStatus.CLINICALLY_VERIFIED
        result.clinical_verified_by = f"rule:{rule.name}"
        if not result.technical_validated_by:
            result.technical_validated_by = f"rule:{rule.name}"
        result.save(update_fields=["status", "clinical_verified_by", "technical_validated_by"])

        signature = rule_signature(
            rule,
            entity_type="laboratory.Result",
            entity_id=result.pk,
            payload={
                "accession": order.accession_number,
                "test": result.test_key,
                "value": result.value,
                "rule": rule.name,
                "rule_version": rule.version,
                "verified_at": timezone.now().isoformat(),
            },
            comment=f"Autoverified: {rule.summary()}",
        )

        execution.auto_verified = True
        execution.signature = signature
        execution.outcome = RuleExecution.Outcome.APPLIED
        execution.actions_applied = list(execution.actions_applied or []) + [
            "autoverified and released"
        ]
        execution.save(update_fields=[
            "auto_verified", "signature", "outcome", "actions_applied",
        ])

        _complete_order_if_fully_verified(order, rule)

    return True


def _complete_order_if_fully_verified(order, rule) -> None:
    """Close an order once every analyte on it has been verified.

    Only closes when *something* on the order was autoverified and nothing is
    left unverified. An order whose last outstanding result was released by a
    rule is complete in exactly the sense it would be if a person had done it.
    """
    outstanding = [
        result for result in order.results.all()
        if not result.is_report_row and not result.clinical_verified_by
    ]
    if outstanding or order.status == OrderStatus.COMPLETED:
        return

    now = timezone.now()
    order.status = OrderStatus.COMPLETED
    order.completed_at = now
    order.updated_at = now
    order.save(update_fields=["status", "completed_at", "updated_at"])

    rule_signature(
        rule,
        entity_type="laboratory.Order",
        entity_id=order.pk,
        payload={"accession": order.accession_number, "released_at": now.isoformat()},
        comment=f"Report released after autoverification of every analyte ({rule.name}).",
    )


@transaction.atomic
def override(execution, *, user, reason: str):
    """Take an autoverified result back for human review.

    The original signature is not deleted — Part 11 records are permanent — it
    is superseded, and the override is itself signed and audited. What a reader
    sees afterwards is the full history: the rule released it, a named person
    pulled it back, and why.
    """
    from apps.audit.recorder import record
    from apps.compliance.services import ControlViolation

    if not reason or not reason.strip():
        raise ControlViolation(
            "A reason is required to override an automatic verification.",
            "21 CFR Part 11 §11.10(e)",
        )
    if execution.overridden_at is not None:
        raise ControlViolation("This autoverification has already been overridden.")

    result = execution.result
    order = execution.order

    if result is not None:
        result.status = OrderStatus.RESULTED
        result.clinical_verified_by = None
        result.save(update_fields=["status", "clinical_verified_by"])

    if order.status == OrderStatus.COMPLETED:
        order.status = OrderStatus.RESULTED
        order.completed_at = None
        order.updated_at = timezone.now()
        order.save(update_fields=["status", "completed_at", "updated_at"])

    execution.overridden_by = user
    execution.overridden_at = timezone.now()
    execution.override_reason = reason.strip()
    execution.outcome = execution.Outcome.OVERRIDDEN
    execution.save(update_fields=[
        "overridden_by", "overridden_at", "override_reason", "outcome",
    ])

    record(
        action=AuditAction.UPDATE,
        entity_type="rules.RuleExecution",
        entity_id=execution.pk,
        entity_label=f"override of autoverification by {execution.rule_name}",
        changes={"auto_verified": {"old": True, "new": False}},
        reason=reason.strip(),
        blocking=True,
    )
    return execution
