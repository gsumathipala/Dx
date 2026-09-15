"""A general rule engine for laboratory decision support.

Every laboratory encodes the same kinds of knowledge: *a potassium above 6.0
on a haemolysed sample gets a suppression comment*, *a TSH outside range on a
patient over 60 gets an interpretive note*, *a normal routine chemistry on a
well-controlled analyser can be released without a human reading it*. In most
systems this lives in somebody's head, in a laminated sheet by the bench, or —
worse — hard-coded.

Here it is data. A rule is a set of conditions over the facts available at the
moment a result is produced, and a set of actions to take when they hold. The
laboratory writes them; nobody edits code.

Design notes
------------
**Conditions are grouped.** Conditions inside a group are ANDed; groups are
ORed. That is enough to express everything a laboratory has ever asked us for
without a parenthesised expression language, and — more importantly — it can be
rendered as a form that a biomedical scientist can read and check. A rule
nobody can read is a rule nobody can validate, and an unvalidatable rule is a
CLIA finding.

**Rules are versioned and signed.** Changing a rule that affects reported
results is a change to the examination process (CLIA §493.1253, ISO 15189
§8.5). Editing a rule increments its version and clears its approval, so a
modified rule does not keep running on the strength of last year's sign-off.

**Every firing is recorded.** ``RuleExecution`` keeps the facts the rule saw
and what it did, so "why does this report say that?" is answerable months
later without re-deriving anything.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import ActivatableModel, IdentifiedModel


class Rule(IdentifiedModel, ActivatableModel):
    """One decision-support rule: when these facts hold, do these things."""

    class Trigger(models.TextChoices):
        RESULT_ENTERED = "result_entered", "A result is entered or corrected"
        RESULT_VALIDATED = "result_validated", "A result is technically validated"
        ORDER_CREATED = "order_created", "An order is accessioned"

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(
        blank=True,
        help_text="What this rule is for, in the words the laboratory would use.",
    )
    trigger = models.CharField(
        max_length=32, choices=Trigger.choices, default=Trigger.RESULT_ENTERED
    )

    #: Narrowing the rule to one analyte or one discipline. Both blank means
    #: the rule is evaluated for every result, which is occasionally what you
    #: want (a haemolysis suppression rule, say) and usually is not.
    test = models.ForeignKey(
        "laboratory.TestDefinition", null=True, blank=True, on_delete=models.CASCADE,
        related_name="rules", help_text="Leave blank to evaluate for every test.",
    )
    department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="rules", help_text="Leave blank to evaluate for every discipline.",
    )

    priority = models.PositiveIntegerField(
        default=100, help_text="Lower numbers are evaluated first."
    )
    stop_on_match = models.BooleanField(
        default=False,
        help_text="When this rule matches, skip every later rule for this result.",
    )

    # ── Change control (CLIA §493.1253, ISO 15189 §8.5, 21 CFR 11 §11.10(a)) ──
    version = models.PositiveIntegerField(default=1, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="approved_rules", editable=False,
    )
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_version = models.PositiveIntegerField(null=True, blank=True, editable=False)
    change_control = models.ForeignKey(
        "compliance.ChangeControl", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="rules", help_text="The change record authorising this rule.",
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "rules"
        ordering = ["priority", "name"]
        indexes = [
            models.Index(fields=["trigger", "active", "priority"]),
            models.Index(fields=["test", "active"]),
        ]

    def __str__(self) -> str:
        return self.name

    # ── Approval state ───────────────────────────────────────────────────────

    @property
    def is_approved(self) -> bool:
        """Whether the *current* version has been signed off."""
        return self.approved_at is not None and self.approved_version == self.version

    @property
    def is_live(self) -> bool:
        """Whether this rule will actually be evaluated.

        An unapproved rule never fires. That is the whole point of versioning
        it: editing a rule withdraws it until somebody competent looks again.
        """
        return self.active and self.is_approved

    @property
    def status_label(self) -> str:
        if not self.active:
            return "Disabled"
        if not self.is_approved:
            return f"Draft v{self.version} — awaiting approval"
        return f"Live (v{self.version})"

    @property
    def has_auto_verify(self) -> bool:
        return any(
            action.kind == RuleAction.Kind.AUTO_VERIFY for action in self.actions.all()
        )

    def bump_version(self) -> None:
        """Record an edit: new version, approval withdrawn."""
        self.version += 1
        self.approved_by = None
        self.approved_at = None
        self.approved_version = None
        self.updated_at = timezone.now()

    def summary(self) -> str:
        """A one-line rendering of the whole rule, for lists and audit labels."""
        groups: dict[int, list[str]] = {}
        for condition in self.conditions.all():
            groups.setdefault(condition.group, []).append(condition.describe())
        clauses = [" AND ".join(parts) for _group, parts in sorted(groups.items())]
        when = " OR ".join(f"({clause})" for clause in clauses) if clauses else "always"
        then = ", ".join(action.describe() for action in self.actions.all()) or "no action"
        return f"When {when} → {then}"


class RuleCondition(IdentifiedModel):
    """One test of one fact.

    ``subject`` names a fact the engine computes for every result (see
    ``apps.rules.engine.build_facts``). Keeping the vocabulary closed means the
    builder can offer a dropdown and the engine can never be handed an
    expression it cannot evaluate.
    """

    class Subject(models.TextChoices):
        RESULT_VALUE = "result.value", "Result — numeric value"
        RESULT_TEXT = "result.text", "Result — text value"
        RESULT_FLAG = "result.flag", "Result — flag (Normal/Low/High/Critical …)"
        RESULT_POSITION = "result.position", "Result — position vs reference interval"
        RESULT_IS_CRITICAL = "result.is_critical", "Result — is a critical value"
        RESULT_HAS_DELTA = "result.has_delta", "Result — triggered a delta check"
        TEST_CODE = "test.code", "Test — code"
        TEST_DEPARTMENT = "test.department", "Test — department"
        PATIENT_AGE_YEARS = "patient.age_years", "Patient — age in years"
        PATIENT_AGE_DAYS = "patient.age_days", "Patient — age in days"
        PATIENT_SEX = "patient.sex", "Patient — sex"
        ORDER_PRIORITY = "order.priority", "Order — priority"
        ORDER_ICD10 = "order.icd10", "Order — ICD-10 diagnosis codes"
        SPECIMEN_TYPE = "specimen.type", "Specimen — type"
        SPECIMEN_CONDITION = "specimen.condition", "Specimen — condition at reception"
        PRIOR_VALUE = "prior.value", "Previous result — numeric value"
        PRIOR_AGE_DAYS = "prior.age_days", "Previous result — days ago"
        DELTA_PERCENT = "delta.percent", "Change from previous — percent"
        DELTA_ABSOLUTE = "delta.absolute", "Change from previous — absolute"
        QC_STATUS = "qc.status", "Quality control — status for this test"
        ENTERED_BY_SOURCE = "entry.source", "Entry — source (manual or instrument)"

    class Operator(models.TextChoices):
        EQ = "eq", "is"
        NE = "ne", "is not"
        LT = "lt", "is less than"
        LTE = "lte", "is at most"
        GT = "gt", "is greater than"
        GTE = "gte", "is at least"
        BETWEEN = "between", "is between"
        IN = "in", "is one of"
        NOT_IN = "not_in", "is not one of"
        CONTAINS = "contains", "contains"
        BLANK = "blank", "is blank"
        NOT_BLANK = "not_blank", "is not blank"

    #: Operators that need no ``value`` at all.
    UNARY = frozenset({Operator.BLANK, Operator.NOT_BLANK})
    #: Operators that read ``value_to`` as well.
    BINARY = frozenset({Operator.BETWEEN})
    #: Operators whose ``value`` is a comma-separated list.
    LIST_OPERATORS = frozenset({Operator.IN, Operator.NOT_IN})
    #: Subjects whose fact is numeric; comparison coerces both sides.
    NUMERIC_SUBJECTS = frozenset({
        Subject.RESULT_VALUE, Subject.PATIENT_AGE_YEARS, Subject.PATIENT_AGE_DAYS,
        Subject.PRIOR_VALUE, Subject.PRIOR_AGE_DAYS, Subject.DELTA_PERCENT,
        Subject.DELTA_ABSOLUTE,
    })
    #: Subjects whose fact is a boolean.
    BOOLEAN_SUBJECTS = frozenset({Subject.RESULT_IS_CRITICAL, Subject.RESULT_HAS_DELTA})

    rule = models.ForeignKey(Rule, on_delete=models.CASCADE, related_name="conditions")
    group = models.PositiveSmallIntegerField(
        default=0,
        help_text="Conditions in the same group must all hold; any group may match.",
    )
    subject = models.CharField(max_length=32, choices=Subject.choices)
    operator = models.CharField(max_length=16, choices=Operator.choices, default=Operator.EQ)
    value = models.CharField(max_length=255, blank=True)
    value_to = models.CharField(max_length=255, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "rule_conditions"
        ordering = ["group", "position"]

    def __str__(self) -> str:
        return self.describe()

    def describe(self) -> str:
        subject = self.get_subject_display()
        operator = self.get_operator_display()
        if self.operator in self.UNARY:
            return f"{subject} {operator}"
        if self.operator in self.BINARY:
            return f"{subject} {operator} {self.value} and {self.value_to}"
        return f"{subject} {operator} {self.value}"


class RuleAction(IdentifiedModel):
    """One thing a matching rule does."""

    class Kind(models.TextChoices):
        APPEND_COMMENT = "append_comment", "Append an interpretive comment"
        SET_FLAG = "set_flag", "Add a result flag"
        ADD_TEST = "add_test", "Add a follow-on test to the order"
        AUTO_VERIFY = "auto_verify", "Request automatic verification"
        HOLD = "hold", "Hold the result from release"
        RAISE_EXCEPTION = "raise_exception", "Raise an item on the exception queue"
        NOTIFY = "notify", "Send an internal message"

    rule = models.ForeignKey(Rule, on_delete=models.CASCADE, related_name="actions")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    text = models.TextField(
        blank=True,
        help_text="Comment text, exception description or message body, as appropriate.",
    )
    flag = models.CharField(
        max_length=64, blank=True, help_text="For 'Add a result flag': the flag to add."
    )
    add_test = models.ForeignKey(
        "laboratory.TestDefinition", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="added_by_rules",
    )
    recipient_role = models.CharField(
        max_length=32, blank=True, help_text="For 'Send an internal message': which role."
    )
    severity = models.CharField(
        max_length=16, blank=True, default="medium",
        help_text="For 'Raise an item on the exception queue'.",
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "rule_actions"
        ordering = ["position"]

    def __str__(self) -> str:
        return self.describe()

    def describe(self) -> str:
        label = self.get_kind_display().lower()
        if self.kind == self.Kind.APPEND_COMMENT:
            excerpt = (self.text or "")[:60]
            return f'{label} "{excerpt}{"…" if len(self.text or "") > 60 else ""}"'
        if self.kind == self.Kind.SET_FLAG:
            return f"{label} {self.flag}"
        if self.kind == self.Kind.ADD_TEST:
            return f"{label} {self.add_test.code if self.add_test else '?'}"
        if self.kind == self.Kind.NOTIFY:
            return f"{label} to {self.recipient_role or 'the laboratory'}"
        return label


class RuleExecutionQuerySet(models.QuerySet):
    def auto_verified(self):
        return self.filter(auto_verified=True)

    def overridable(self):
        return self.filter(auto_verified=True, overridden_at__isnull=True)


class RuleExecution(IdentifiedModel):
    """A record of one rule being evaluated against one result.

    Only matches are stored. Recording every non-match would multiply the row
    count by the size of the rule set for no diagnostic gain — a rule that did
    not fire is visible by simulating it against the stored facts.
    """

    class Outcome(models.TextChoices):
        APPLIED = "applied", "Actions applied"
        PARTIAL = "partial", "Some actions refused"
        BLOCKED = "blocked", "All actions refused"
        OVERRIDDEN = "overridden", "Overridden by a user"

    rule = models.ForeignKey(
        Rule, null=True, on_delete=models.SET_NULL, related_name="executions"
    )
    rule_name = models.CharField(max_length=255)
    rule_version = models.PositiveIntegerField(default=1)

    order = models.ForeignKey(
        "laboratory.Order", on_delete=models.CASCADE, related_name="rule_executions"
    )
    result = models.ForeignKey(
        "laboratory.Result", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="rule_executions",
    )
    test_code = models.CharField(max_length=64, blank=True)

    fired_at = models.DateTimeField(default=timezone.now)
    facts = models.JSONField(default=dict, blank=True)
    actions_applied = models.JSONField(default=list, blank=True)
    refusals = models.JSONField(
        default=list, blank=True,
        help_text="Guardrails that refused an action, with the reason.",
    )
    outcome = models.CharField(max_length=16, choices=Outcome.choices, default=Outcome.APPLIED)
    auto_verified = models.BooleanField(default=False)
    signature = models.ForeignKey(
        "compliance.ElectronicSignature", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="rule_executions",
    )

    overridden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="rule_overrides",
    )
    overridden_at = models.DateTimeField(null=True, blank=True)
    override_reason = models.TextField(blank=True)

    objects = RuleExecutionQuerySet.as_manager()

    class Meta:
        db_table = "rule_executions"
        ordering = ["-fired_at"]
        indexes = [
            models.Index(fields=["order", "-fired_at"]),
            models.Index(fields=["-fired_at"]),
            models.Index(fields=["auto_verified", "-fired_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.rule_name} on {self.order_id}/{self.test_code}"

    @property
    def is_overridden(self) -> bool:
        return self.overridden_at is not None

    # ── Redacted views, for roles barred from patient data ───────────────────
    #
    # The facts a rule saw are patient data: an age, a sex, a diagnosis code
    # and an analyte value identify a person far more readily than most people
    # expect. Someone checking that the engine is running needs the rule, the
    # time and the outcome, and none of that.

    @property
    def safe_facts(self) -> str:
        return f"[redacted — {len(self.facts or {})} facts]"

    @property
    def safe_test_code(self) -> str:
        return "[redacted]"
