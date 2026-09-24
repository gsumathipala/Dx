"""Cross-cutting integrity checks over the whole workflow.

The test suite proves each piece behaves correctly in isolation. This asks a
different question: *is the data in this installation self-consistent right
now?* Those are not the same thing, and the gap between them is where real
laboratories live — a reference interval edited after results were released, an
order marked complete while one analyte is still unverified, an interface
configured bidirectional with an empty code map that answers analysers in a
vocabulary they do not speak.

None of that is a bug in the code. All of it is wrong, and none of it surfaces
on any screen.

Severity means something
------------------------
``ERROR`` — the data contradicts itself. Something has gone wrong and a person
must look. These fail the command's exit status so a nightly job can gate on it.

``WARN`` — consistent, but operationally wrong or heading that way.

``INFO`` — worth knowing; no action implied.

Every check names the records it found, capped, so the output is actionable
rather than a number to feel bad about.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger("dx.integrity")

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"
#: Examples listed per finding. Enough to start investigating, not a data dump.
EXAMPLE_LIMIT = 5


@dataclass
class Finding:
    """One integrity problem: what, how bad, how many, and which records.

    ``examples`` is capped so output stays readable; ``count`` is the true
    total so the scale is still visible.
    """

    code: str
    severity: str
    title: str
    detail: str
    count: int = 0
    examples: list[str] = field(default_factory=list)

    @property
    def is_error(self) -> bool:
        return self.severity == ERROR

    def __str__(self) -> str:
        head = f"[{self.severity}] {self.code}: {self.title} ({self.count})"
        if self.examples:
            head += "\n    " + "\n    ".join(self.examples)
        return head


def _finding(code, severity, title, detail, rows, label=str) -> Finding | None:
    """Build a finding from a queryset, or None when it is empty."""
    rows = list(rows[:200])
    if not rows:
        return None
    return Finding(
        code=code, severity=severity, title=title, detail=detail,
        count=len(rows),
        examples=[label(row) for row in rows[:EXAMPLE_LIMIT]],
    )


# ── The audit trail ──────────────────────────────────────────────────────────


def check_audit() -> list[Finding]:
    """The trail verifies, and is still protected at the database level.

    Run first and reported first: if the chain does not verify, nothing else
    in the report can be relied on.
    """
    from apps.audit.models import AuditEvent
    from apps.audit.protection import is_installed
    from apps.audit.verification import verify_chain

    findings: list[Finding] = []

    if not is_installed():
        findings.append(Finding(
            code="AUDIT-TRIGGERS", severity=ERROR,
            title="The append-only database triggers are not installed",
            detail=(
                "Without them the audit trail is protected only by the ORM, and "
                "anything with a database connection can rewrite history. "
                "Reinstall with apps.audit.protection.install()."
            ),
            count=1,
        ))

    try:
        outcome = verify_chain()
    except Exception as error:  # a verification that cannot run is itself a finding
        findings.append(Finding(
            code="AUDIT-CHAIN", severity=ERROR,
            title="The audit chain could not be verified",
            detail=str(error), count=1,
        ))
        return findings

    problems = outcome.problems
    if problems:
        findings.append(Finding(
            code="AUDIT-CHAIN", severity=ERROR,
            title="The audit chain does not verify",
            detail=(
                "An event has been altered or removed. Nothing else in this "
                "report can be trusted until this is explained."
            ),
            count=len(problems),
            examples=[str(problem)[:160] for problem in problems[:EXAMPLE_LIMIT]],
        ))
    else:
        findings.append(Finding(
            code="AUDIT-OK", severity=INFO,
            title=f"Audit chain verified — {outcome.checked} event(s) through "
                  f"#{outcome.head_sequence or 0}",
            detail="", count=outcome.checked,
        ))
    return findings


# ── Accessioning and specimens ───────────────────────────────────────────────


def check_accessioning() -> list[Finding]:
    """Every result traces back to a specimen somebody accessioned."""
    from apps.common.constants import OrderStatus
    from apps.laboratory.models import Order

    findings = []

    # An order awaiting collection has no specimen, which is not a defect. The
    # integrity problem is a result existing for a specimen nobody accessioned:
    # something was measured and there is no record of what it was measured on.
    stranded = Order.objects.filter(
        specimens__isnull=True, results__isnull=False,
    ).exclude(
        status__in=[OrderStatus.CANCELLED, OrderStatus.REJECTED]
    ).select_related("patient").distinct()
    findings.append(_finding(
        "ORDER-NO-SPECIMEN", ERROR,
        "Orders carrying results with no specimen ever accessioned",
        "Something was measured and there is no record of what it was measured "
        "on. The chain of custody for these results is broken.",
        stranded, lambda order: f"{order.accession_number} ({order.status})",
    ))

    completed_without_results = Order.objects.filter(
        status=OrderStatus.COMPLETED, results__isnull=True
    )
    findings.append(_finding(
        "ORDER-COMPLETE-EMPTY", ERROR,
        "Orders marked complete with no results at all",
        "A completed order with nothing in it was reported to somebody as "
        "finished. This should not be reachable through any screen.",
        completed_without_results, lambda order: order.accession_number,
    ))
    return [f for f in findings if f]


# ── Results, validation and verification ─────────────────────────────────────


def check_results() -> list[Finding]:
    """Verification is attributable, complete, and still agrees with the catalogue.

    The expensive checks here are deliberately capped (2,000–5,000 rows): this
    is a consistency sweep, not an exhaustive audit, and an unbounded scan on a
    large installation would make nobody run it.
    """
    from apps.common.constants import OrderStatus
    from apps.laboratory.models import Order, Result

    findings = []

    unattributed = Result.objects.filter(
        status=OrderStatus.CLINICALLY_VERIFIED, clinical_verified_by__isnull=True,
    ).exclude(test_key=Result.REPORT_TEST_ID)
    findings.append(_finding(
        "RESULT-UNATTRIBUTED", ERROR,
        "Verified results with no verifier recorded",
        "CLIA §493.1291(c) requires the report to identify who released the "
        "result. A verified result naming nobody cannot be defended.",
        unattributed.select_related("order"),
        lambda r: f"{r.order.accession_number}/{r.test_key}",
    ))

    # An order is complete only when every analyte on it has been verified.
    incomplete = []
    for order in Order.objects.filter(
        status=OrderStatus.COMPLETED
    ).prefetch_related("results")[:2000]:
        outstanding = [
            result for result in order.results.all()
            if not result.is_report_row and not result.clinical_verified_by
        ]
        if outstanding:
            incomplete.append(
                f"{order.accession_number} — {len(outstanding)} unverified"
            )
    if incomplete:
        findings.append(Finding(
            code="ORDER-COMPLETE-UNVERIFIED", severity=ERROR,
            title="Orders marked complete with unverified analytes",
            detail=(
                "The report went out while part of it had not been verified by "
                "anybody. Check whether it was distributed."
            ),
            count=len(incomplete), examples=incomplete[:EXAMPLE_LIMIT],
        ))

    # The numeric shadow column drifting from the stored text means trending,
    # delta checks and every rule silently stop seeing the result.
    drifted = []
    for result in Result.objects.filter(
        numeric_value__isnull=True
    ).exclude(value__isnull=True).exclude(value="")[:5000]:
        try:
            float(result.value)
        except (TypeError, ValueError):
            continue
        drifted.append(f"{result.order_id}/{result.test_key} = {result.value}")
    if drifted:
        findings.append(Finding(
            code="RESULT-NUMERIC-DRIFT", severity=ERROR,
            title="Numeric results whose numeric column was never populated",
            detail=(
                "The value parses as a number but numeric_value is null, so "
                "delta checks, trending and every decision rule are blind to "
                "it. Usually caused by a bulk write that bypassed Result.save()."
            ),
            count=len(drifted), examples=drifted[:EXAMPLE_LIMIT],
        ))

    # Flags that no longer match the interval they were computed against.
    stale = []
    for result in Result.objects.filter(
        numeric_value__isnull=False, test__isnull=False
    ).select_related("test")[:5000]:
        expected = result.test.evaluate(result.numeric_value)
        expected_flags = [] if expected == "Normal" else [expected]
        current = [f for f in (result.result_flags or []) if f in {
            "Low", "High", "Critical Low", "Critical High", "Normal"
        }]
        if sorted(current) != sorted(expected_flags):
            stale.append(
                f"{result.order_id}/{result.test_key}: stored {current or 'none'}, "
                f"interval now says {expected_flags or 'none'}"
            )
    if stale:
        findings.append(Finding(
            code="RESULT-FLAGS-STALE", severity=WARN,
            title="Results whose flags disagree with the current reference interval",
            detail=(
                "Expected after an interval is edited: the stored flag is what "
                "was reported at the time and is deliberately not rewritten. "
                "Worth confirming the edit was intended, and whether anything "
                "released against the old interval needs review."
            ),
            count=len(stale), examples=stale[:EXAMPLE_LIMIT],
        ))
    return [f for f in findings if f]


# ── Critical values ──────────────────────────────────────────────────────────


def check_critical_values() -> list[Finding]:
    """Every critical result reached a person, and is on somebody's list."""
    from apps.clinical.models import CriticalValueNotification
    from apps.laboratory.models import Result

    findings = []

    overdue = CriticalValueNotification.objects.filter(
        status=CriticalValueNotification.Status.PENDING,
        escalation_due_at__lt=timezone.now(),
    ).select_related("order")
    findings.append(_finding(
        "CRITICAL-OVERDUE", ERROR,
        "Critical values past their escalation deadline, unacknowledged",
        "Nobody has recorded telephoning these. CAP GEN.41320 requires "
        "documented notification with read-back.",
        overdue, lambda n: f"{n.order.accession_number} {n.test_code} = {n.value}",
    ))

    # A critically flagged result that never raised a notification means the
    # clinical engine did not run — typically a bulk or migrated write.
    missed = []
    flagged = Result.objects.filter(
        result_flags__contains=["Critical High"]
    ) | Result.objects.filter(result_flags__contains=["Critical Low"])
    for result in flagged.select_related("order", "test").distinct()[:2000]:
        if result.test_id is None:
            continue
        if not CriticalValueNotification.objects.filter(
            order=result.order, test=result.test
        ).exists():
            missed.append(f"{result.order.accession_number}/{result.test_key}")
    if missed:
        findings.append(Finding(
            code="CRITICAL-NOT-RAISED", severity=ERROR,
            title="Critically flagged results with no notification raised",
            detail=(
                "The result is flagged critical but no notification exists, so "
                "nobody was ever prompted to telephone it. Usually a write that "
                "bypassed the clinical engine."
            ),
            count=len(missed), examples=missed[:EXAMPLE_LIMIT],
        ))
    return [f for f in findings if f]


# ── Quality control and autoverification ─────────────────────────────────────


def check_quality() -> list[Finding]:
    """Autoverification is configured so it can actually release something.

    Both findings here describe a *safe* misconfiguration — nothing is released
    — but one where the configuration claims something the system cannot
    honour, which is how a laboratory concludes the feature is broken.
    """
    from apps.laboratory.models import TestDefinition
    from apps.quality.models import QcDefinition, QcRun

    findings = []

    permitted = TestDefinition.objects.filter(auto_verify_permitted=True, active=True)
    without_qc = [
        test for test in permitted
        if not QcDefinition.objects.filter(test_code=test.code).exists()
    ]
    if without_qc:
        findings.append(Finding(
            code="AUTOVERIFY-NO-QC", severity=ERROR,
            title="Analytes approved for autoverification with no QC target defined",
            detail=(
                "Autoverification requires QC to be in control, and there is "
                "nothing here to be in control of. Every release will be "
                "refused — which is safe, but means the configuration says "
                "something the system cannot honour."
            ),
            count=len(without_qc), examples=[t.code for t in without_qc[:EXAMPLE_LIMIT]],
        ))

    no_interval = [
        test for test in permitted
        if test.normal_low is None and test.normal_high is None
    ]
    if no_interval:
        findings.append(Finding(
            code="AUTOVERIFY-NO-INTERVAL", severity=ERROR,
            title="Analytes approved for autoverification with no reference interval",
            detail=(
                "'Within the reference interval' has no meaning without one, so "
                "nothing will ever be released for these analytes."
            ),
            count=len(no_interval), examples=[t.code for t in no_interval[:EXAMPLE_LIMIT]],
        ))

    unresolved = QcRun.objects.filter(
        status=QcRun.Status.FAIL, corrective_action__isnull=True,
        timestamp__gte=timezone.now() - timedelta(days=30),
    ).select_related("definition")
    findings.append(_finding(
        "QC-FAIL-NO-CAPA", WARN,
        "Failed QC runs in the last 30 days with no corrective action",
        "CLIA §493.1256(d) expects a failed run to be investigated. An "
        "uninvestigated failure blocks patient results and nobody is working on it.",
        unresolved,
        lambda run: f"{run.definition.test_code if run.definition_id else '?'} = {run.value}",
    ))
    return [f for f in findings if f]


# ── Decision rules ───────────────────────────────────────────────────────────


def check_rules() -> list[Finding]:
    """Rules that somebody believes are running actually are."""
    from apps.rules.models import Rule, RuleAction

    findings = []

    unapproved_live = [
        rule for rule in Rule.objects.filter(active=True).prefetch_related("actions")
        if not rule.is_approved
    ]
    if unapproved_live:
        findings.append(Finding(
            code="RULE-UNAPPROVED", severity=WARN,
            title="Active rules awaiting approval, so not firing",
            detail=(
                "Enabled but unapproved. Somebody probably believes these are "
                "running. Editing a rule withdraws approval, which is the usual "
                "cause."
            ),
            count=len(unapproved_live),
            examples=[f"{r.name} (v{r.version})" for r in unapproved_live[:EXAMPLE_LIMIT]],
        ))

    mismatched = []
    for rule in Rule.objects.filter(active=True).select_related("test").prefetch_related("actions"):
        if not rule.actions.filter(kind=RuleAction.Kind.AUTO_VERIFY).exists():
            continue
        if rule.test is None:
            mismatched.append(f"{rule.name}: applies to every test")
        elif not rule.test.auto_verify_permitted:
            mismatched.append(f"{rule.name}: {rule.test.code} is not permitted")
    if mismatched:
        findings.append(Finding(
            code="RULE-AUTOVERIFY-MISMATCH", severity=WARN,
            title="Autoverification rules that can never release anything",
            detail=(
                "The rule asks for automatic release on an analyte the "
                "laboratory has not approved for it, so every attempt is "
                "refused. Safe, but the intent and the configuration disagree."
            ),
            count=len(mismatched), examples=mismatched[:EXAMPLE_LIMIT],
        ))

    unconditional = [
        rule for rule in Rule.objects.filter(active=True).prefetch_related("conditions")
        if rule.is_approved and not rule.conditions.exists()
    ]
    if unconditional:
        findings.append(Finding(
            code="RULE-UNCONDITIONAL", severity=WARN,
            title="Approved rules with no conditions — these match every result",
            detail=(
                "Occasionally intended (a standard footnote), usually not. "
                "Check each one is meant to fire on everything it sees."
            ),
            count=len(unconditional),
            examples=[r.name for r in unconditional[:EXAMPLE_LIMIT]],
        ))
    return [f for f in findings if f]


# ── Interfaces and integrations ──────────────────────────────────────────────


def check_interfaces() -> list[Finding]:
    """Analysers and integrations are talking, and credentials are accountable."""
    from apps.api.models import ApiClient, PHI_SCOPES, WebhookDelivery
    from apps.interop.models import InstrumentInterface

    findings = []

    stale = [i for i in InstrumentInterface.objects.filter(enabled=True) if i.is_stale]
    if stale:
        findings.append(Finding(
            code="INTERFACE-SILENT", severity=WARN,
            title="Enabled instrument interfaces that have sent nothing for over an hour",
            detail="Results may be accumulating on the analyser.",
            count=len(stale), examples=[i.name for i in stale[:EXAMPLE_LIMIT]],
        ))

    unmapped = InstrumentInterface.objects.filter(
        enabled=True, direction=InstrumentInterface.Direction.BIDIRECTIONAL,
    ).exclude(test_code_map__isnull=True)
    unmapped = [i for i in unmapped if not i.test_code_map]
    if unmapped:
        findings.append(Finding(
            code="INTERFACE-NO-CODEMAP", severity=ERROR,
            title="Bidirectional interfaces with an empty test code map",
            detail=(
                "Host query answers the analyser in Dx test codes, which it "
                "will not recognise — so it runs nothing, or the wrong thing. "
                "Populate the code map before enabling host query."
            ),
            count=len(unmapped), examples=[i.name for i in unmapped[:EXAMPLE_LIMIT]],
        ))

    failed = WebhookDelivery.objects.filter(
        status=WebhookDelivery.Status.FAILED
    ).select_related("webhook")
    findings.append(_finding(
        "WEBHOOK-FAILED", WARN,
        "Webhook deliveries that gave up",
        "A subscriber has stopped receiving events. An integration that quietly "
        "stopped working is how a ward learns of a result by telephone.",
        failed, lambda d: f"{d.webhook.name} — {d.event}",
    ))

    loose = [
        client for client in ApiClient.objects.filter(active=True)
        if PHI_SCOPES.intersection(client.scopes or [])
        and not (client.purpose or "").strip()
    ]
    if loose:
        findings.append(Finding(
            code="API-NO-PURPOSE", severity=ERROR,
            title="API clients holding patient-data scopes with no stated purpose",
            detail=(
                "The purpose appears on every disclosure record the client "
                "generates. Without it the disclosure accounting is incomplete "
                "(HIPAA §164.528)."
            ),
            count=len(loose), examples=[c.name for c in loose[:EXAMPLE_LIMIT]],
        ))

    expired = ApiClient.objects.filter(active=True, expires_at__lt=timezone.now())
    findings.append(_finding(
        "API-EXPIRED-ACTIVE", WARN,
        "API clients past their expiry but still marked active",
        "They are refused at authentication, so this is tidiness rather than "
        "exposure — but an expired credential left active hides whether it is "
        "still wanted.",
        expired, lambda c: c.name,
    ))
    return [f for f in findings if f]


# ── Continuity, locking and compliance ───────────────────────────────────────


def check_operations() -> list[Finding]:
    """Continuity and statutory obligations are not quietly lapsing."""
    from apps.accounts.models import RecordLock
    from apps.compliance.models import DataSubjectRequest
    from apps.operations.models import DowntimeEvent, DowntimePack, ExceptionItem

    findings = []

    unreconciled = DowntimeEvent.objects.filter(
        ended_at__isnull=False, reconciled_at__isnull=True
    )
    findings.append(_finding(
        "DOWNTIME-UNRECONCILED", ERROR,
        "Past outages whose paper results have not been confirmed entered",
        "An outage is closed when the paper results are in, not when the server "
        "came back. Until this is reconciled, nobody has confirmed nothing was lost.",
        unreconciled, lambda e: f"{e.reference} ended {e.ended_at:%Y-%m-%d}",
    ))

    latest_pack = DowntimePack.objects.first()
    if latest_pack is None:
        findings.append(Finding(
            code="DOWNTIME-NO-PACK", severity=ERROR,
            title="No downtime pack has ever been generated",
            detail=(
                "If the system became unavailable now, the laboratory would "
                "have no record of what was outstanding. Schedule "
                "`manage.py downtime_pack`."
            ),
            count=1,
        ))
    elif latest_pack.is_stale:
        findings.append(Finding(
            code="DOWNTIME-PACK-STALE", severity=WARN,
            title=f"The newest downtime pack is {latest_pack.age_hours:.0f} hours old",
            detail="A stale pack is a trap, not a safety net — people trust it.",
            count=1, examples=[latest_pack.path],
        ))

    expired_locks = RecordLock.objects.filter(expires_at__lte=timezone.now())
    findings.append(_finding(
        "LOCK-EXPIRED", INFO,
        "Expired record locks not yet cleaned up",
        "Harmless — expired locks are ignored — but they accumulate. "
        "`apps.accounts.locking.purge_all_expired()` clears them.",
        expired_locks, lambda lock: f"{lock.entity_type} held by {lock.username}",
    ))

    overdue_requests = DataSubjectRequest.objects.overdue()
    findings.append(_finding(
        "GDPR-OVERDUE", ERROR,
        "Data subject requests past their statutory deadline",
        "GDPR Article 12(3) allows one month. The extension must have been "
        "communicated within the first month to be available.",
        overdue_requests, lambda r: f"{r.reference} due {r.due_at:%Y-%m-%d}",
    ))

    aged = ExceptionItem.objects.open().filter(
        severity__in=[ExceptionItem.Severity.CRITICAL, ExceptionItem.Severity.HIGH],
        raised_at__lt=timezone.now() - timedelta(days=7),
    )
    findings.append(_finding(
        "EXCEPTION-AGED", WARN,
        "High or critical exception queue items open for over a week",
        "Either they matter and nobody is working on them, or the severity is "
        "wrong and the queue is training people to ignore it.",
        aged, lambda item: f"{item.title} ({item.get_severity_display()})",
    ))
    return [f for f in findings if f]


# ── Catalogue configuration ──────────────────────────────────────────────────


def check_catalogue() -> list[Finding]:
    """Limits are internally consistent, so flagging means what it says.

    An inverted limit is invisible on the catalogue screen — each field looks
    reasonable alone — and produces either every result flagged or none.
    """
    from apps.clinical.models import DemographicReferenceRange
    from apps.laboratory.models import TestDefinition

    findings = []

    inverted = []
    for test in TestDefinition.objects.filter(active=True):
        low, high = test.normal_low, test.normal_high
        panic_low, panic_high = test.panic_low, test.panic_high
        if low is not None and high is not None and low > high:
            inverted.append(f"{test.code}: reference {low} > {high}")
        if panic_low is not None and panic_high is not None and panic_low > panic_high:
            inverted.append(f"{test.code}: critical {panic_low} > {panic_high}")
        if panic_low is not None and low is not None and panic_low > low:
            inverted.append(f"{test.code}: critical low {panic_low} above reference low {low}")
        if panic_high is not None and high is not None and panic_high < high:
            inverted.append(f"{test.code}: critical high {panic_high} below reference high {high}")
    if inverted:
        findings.append(Finding(
            code="CATALOGUE-INVERTED", severity=ERROR,
            title="Test definitions whose limits are inconsistent",
            detail=(
                "Every result will be flagged, or none will. Both are wrong and "
                "neither is obvious from the screen."
            ),
            count=len(inverted), examples=inverted[:EXAMPLE_LIMIT],
        ))

    no_interval = TestDefinition.objects.filter(active=True).filter(
        reference_range__isnull=True
    )
    findings.append(_finding(
        "CATALOGUE-NO-INTERVAL", WARN,
        "Active tests with no reference interval",
        "Results will never be flagged high or low. Legitimate for a "
        "qualitative test; a defect for a quantitative one.",
        no_interval, lambda test: test.code,
    ))

    bad_demographics = []
    for candidate in DemographicReferenceRange.objects.filter(active=True):
        if (candidate.low_normal is not None and candidate.high_normal is not None
                and candidate.low_normal > candidate.high_normal):
            bad_demographics.append(
                f"{candidate.test_code} {candidate.gender} "
                f"{candidate.age_min}–{candidate.age_max}"
            )
        if (candidate.age_min is not None and candidate.age_max is not None
                and candidate.age_min > candidate.age_max):
            bad_demographics.append(
                f"{candidate.test_code}: age band {candidate.age_min}–{candidate.age_max}"
            )
    if bad_demographics:
        findings.append(Finding(
            code="DEMOGRAPHIC-INVERTED", severity=ERROR,
            title="Demographic reference intervals with inverted bounds",
            detail="These silently never match, or always do.",
            count=len(bad_demographics), examples=bad_demographics[:EXAMPLE_LIMIT],
        ))
    return [f for f in findings if f]


# ── Runner ───────────────────────────────────────────────────────────────────


CHECKS = (
    ("audit trail", check_audit),
    ("accessioning", check_accessioning),
    ("results and verification", check_results),
    ("critical values", check_critical_values),
    ("quality control", check_quality),
    ("decision rules", check_rules),
    ("interfaces and integrations", check_interfaces),
    ("continuity and compliance", check_operations),
    ("test catalogue", check_catalogue),
)


def run_all() -> tuple[list[Finding], dict[str, str]]:
    """Every check. One failing check must not hide the others."""
    findings: list[Finding] = []
    failures: dict[str, str] = {}

    for label, check in CHECKS:
        try:
            findings.extend(check())
        except Exception as error:
            logger.exception("Integrity check %r failed", label)
            failures[label] = str(error)
            findings.append(Finding(
                code="CHECK-FAILED", severity=ERROR,
                title=f"The {label} check could not run",
                detail=str(error)[:500], count=1,
            ))
    return findings, failures


def summarise(findings) -> dict[str, int]:
    counts = {ERROR: 0, WARN: 0, INFO: 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts
