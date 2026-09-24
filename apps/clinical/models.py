"""The clinical decision engine: delta checks, critical values, reflex testing,
demographic reference intervals, calculated tests and notifiable conditions."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import ActivatableModel, IdentifiedModel


class DeltaCheckRule(IdentifiedModel):
    """When to flag a result for changing too much from the patient's last one.

    One rule per analyte. The engine (``apps.clinical.services.run_delta_checks``)
    finds the most recent *earlier* numeric result for the same patient and test
    inside ``lookback_days``, and flags when the change exceeds ``threshold``.

    ``test_code`` duplicates ``test.code`` deliberately: the rule is quoted in
    flags and reports that must still read correctly after a catalogue entry is
    renamed or retired.
    """

    class DeltaType(models.TextChoices):
        # Percent is right for analytes with a wide reference interval
        # (creatinine, ferritin); absolute for narrow ones (sodium), where a
        # 10% change is already implausible.
        PERCENT = "percent", "Percent change"
        ABSOLUTE = "absolute", "Absolute change"

    class Direction(models.TextChoices):
        ANY = "any", "Any direction"
        INCREASE = "increase", "Increase only"
        DECREASE = "decrease", "Decrease only"

    test = models.ForeignKey(
        "laboratory.TestDefinition", on_delete=models.CASCADE, related_name="delta_rules"
    )
    test_code = models.CharField(max_length=64)
    delta_type = models.CharField(max_length=16, choices=DeltaType.choices)
    #: Interpreted as a percentage or in the analyte's own units, depending on
    #: ``delta_type``. There is no unit field: the units are the test's.
    threshold = models.FloatField()
    direction = models.CharField(max_length=16, choices=Direction.choices, default=Direction.ANY)
    #: Bounds the search for a predecessor. Too long and a delta fires on a
    #: genuine clinical change months apart; too short and a sample swap
    #: between admissions goes unnoticed. Thirty days suits most chemistry.
    lookback_days = models.PositiveIntegerField(
        default=30, help_text="How far back to search for a comparable prior result"
    )
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = "delta_check_rules"
        ordering = ["test_code"]

    def __str__(self) -> str:
        unit = "%" if self.delta_type == self.DeltaType.PERCENT else ""
        return f"{self.test_code} Δ{self.threshold}{unit} ({self.direction})"


class DeltaCheckFlag(IdentifiedModel):
    """A result that tripped a delta rule, with the comparison that tripped it.

    Everything needed to re-explain the flag is copied onto the row —
    ``previous_value``, ``previous_timestamp``, both computed deltas — rather
    than recomputed on demand. The predecessor may later be amended, erased
    under GDPR, or moved by a patient merge; the flag still has to say what it
    saw at the time.

    Both ``delta_percent`` and ``delta_absolute`` are stored whichever rule
    fired, because the person reading the flag wants the other one too.
    ``delta_percent`` is null when the previous value was zero.
    """

    order = models.ForeignKey("laboratory.Order", on_delete=models.CASCADE, related_name="delta_flags")
    test = models.ForeignKey(
        "laboratory.TestDefinition", on_delete=models.CASCADE, related_name="delta_flags"
    )
    rule = models.ForeignKey(DeltaCheckRule, on_delete=models.CASCADE, related_name="flags")
    previous_order = models.ForeignKey(
        "laboratory.Order", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="delta_flags_as_previous",
    )
    previous_value = models.FloatField(null=True, blank=True)
    previous_timestamp = models.DateTimeField(null=True, blank=True)
    current_value = models.FloatField()
    delta_percent = models.FloatField(null=True, blank=True)
    delta_absolute = models.FloatField(null=True, blank=True)
    flagged_at = models.DateTimeField(default=timezone.now)
    acknowledged_by = models.CharField(max_length=150, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "delta_check_flags"
        ordering = ["-flagged_at"]
        indexes = [models.Index(fields=["order"]), models.Index(fields=["acknowledged_at"])]

    def __str__(self) -> str:
        return f"Δ {self.test_id} on {self.order_id}"

    @property
    def is_acknowledged(self) -> bool:
        return self.acknowledged_at is not None


class CriticalValueNotificationQuerySet(models.QuerySet):
    def pending(self):
        # The literal rather than Status.PENDING because this manager is
        # attached before the class body finishes; they are the same string and
        # a test asserts it stays that way.
        return self.filter(status="Pending")

    def overdue(self):
        """Pending notifications past their escalation deadline."""
        return self.pending().filter(escalation_due_at__lt=timezone.now())


class CriticalValueNotification(IdentifiedModel):
    """A life-threatening result requiring documented clinician notification.

    CAP requires the read-back of critical values to be recorded: who was told,
    when, by whom, and confirmation that they repeated the value back.
    """

    class CriticalType(models.TextChoices):
        HIGH = "HIGH", "Critically high"
        LOW = "LOW", "Critically low"

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending notification"
        ACKNOWLEDGED = "Acknowledged", "Acknowledged"
        ESCALATED = "Escalated", "Escalated"

    order = models.ForeignKey(
        "laboratory.Order", on_delete=models.CASCADE, related_name="critical_values"
    )
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="critical_values"
    )
    test = models.ForeignKey(
        "laboratory.TestDefinition", on_delete=models.CASCADE, related_name="critical_values"
    )
    #: Copied from the test and result at the moment of raising. A notification
    #: is a record of what was told to whom; it must not change when the
    #: catalogue's critical limits are later revised, or the read-back
    #: documentation would describe a conversation that never happened.
    test_code = models.CharField(max_length=64)
    #: Text, not a float: a critical value may be "<0.1" or "TNP", and the
    #: number shown to the clinician is the number that must be recorded.
    value = models.CharField(max_length=64)
    #: Rendered limit as it stood, e.g. "> 25 mmol/L".
    threshold = models.CharField(max_length=64)
    critical_type = models.CharField(max_length=8, choices=CriticalType.choices)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=150, null=True, blank=True)
    #: Set when the notification is raised — 30 minutes for a STAT order, 60
    #: otherwise. Past this, `sweep_exceptions` puts the notification on the
    #: exception queue, because a critical value nobody acknowledged overnight
    #: is the failure mode this whole model exists to prevent.
    escalation_due_at = models.DateTimeField(
        null=True, blank=True, help_text="Unacknowledged notifications escalate after this time"
    )

    objects = CriticalValueNotificationQuerySet.as_manager()

    class Meta:
        db_table = "critical_value_notifications"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.test_code} {self.value} ({self.critical_type}) for {self.patient_id}"

    @property
    def minutes_outstanding(self) -> float:
        if self.status != self.Status.PENDING:
            return 0.0
        return (timezone.now() - self.created_at).total_seconds() / 60.0

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.status == self.Status.PENDING
            and self.escalation_due_at
            and self.escalation_due_at < timezone.now()
        )


class CriticalValueAcknowledgment(IdentifiedModel):
    """Documented read-back of a critical value.

    Several per notification is normal and correct: the first call reaches a
    ward clerk, the second the on-call doctor. Each attempt is its own row, so
    "we tried for forty minutes" is evidenced rather than asserted.

    ``read_back_confirmed`` is the field an inspector looks at. Telling someone
    a value is not notification; them repeating it back is.
    """

    class Method(models.TextChoices):
        PHONE = "phone", "Telephone"
        IN_PERSON = "in-person", "In person"
        FAX = "fax", "Fax"
        SECURE_MESSAGE = "secure-message", "Secure message"

    notification = models.ForeignKey(
        CriticalValueNotification, on_delete=models.CASCADE, related_name="acknowledgments"
    )
    acknowledged_by = models.CharField(max_length=150)
    acknowledged_at = models.DateTimeField(default=timezone.now)
    notified_clinician = models.CharField(max_length=255, null=True, blank=True)
    notification_method = models.CharField(max_length=32, choices=Method.choices, null=True, blank=True)
    read_back_confirmed = models.BooleanField(
        default=False, help_text="The recipient repeated the result back — CAP GEN.41320"
    )
    notes = models.TextField(null=True, blank=True)
    escalated_to = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "critical_value_acknowledgments"
        ordering = ["-acknowledged_at"]

    def __str__(self) -> str:
        return f"{self.notification_id} acknowledged by {self.acknowledged_by}"


class ReflexRule(IdentifiedModel):
    """Add a follow-on test automatically when a result crosses a threshold.

    The classic case is a raised TSH reflexing to free T4: the clinician asked
    one question, and answering it properly needs a second test on the same
    sample, now, rather than a second visit a week later.

    Deliberately simpler than a :class:`apps.rules.models.Rule`, which can also
    add a test. This is the single-condition form the laboratory configures per
    analyte and can read at a glance; the rules engine is for anything needing
    more than one condition. Both run, and both are idempotent per order.
    """

    class Operator(models.TextChoices):
        GT = ">", "greater than"
        GTE = ">=", "greater than or equal to"
        LT = "<", "less than"
        LTE = "<=", "less than or equal to"
        EQ = "==", "equal to"

    name = models.CharField(max_length=255)
    trigger_test = models.ForeignKey(
        "laboratory.TestDefinition", on_delete=models.CASCADE, related_name="reflex_triggers"
    )
    operator = models.CharField(max_length=4, choices=Operator.choices)
    threshold = models.FloatField()
    add_test = models.ForeignKey(
        "laboratory.TestDefinition", on_delete=models.CASCADE, related_name="reflex_additions"
    )
    add_test_code = models.CharField(max_length=64)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = "reflex_rules"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name}: {self.trigger_test_id} {self.operator} {self.threshold} → {self.add_test_code}"

    def matches(self, value: float) -> bool:
        """Whether this result triggers the reflex.

        An unrecognised operator returns False rather than raising: a rule with
        corrupt configuration must fail closed — adding no test — rather than
        blowing up the result-entry transaction that called it.
        """
        comparisons = {
            self.Operator.GT: value > self.threshold,
            self.Operator.GTE: value >= self.threshold,
            self.Operator.LT: value < self.threshold,
            self.Operator.LTE: value <= self.threshold,
            self.Operator.EQ: value == self.threshold,
        }
        return comparisons.get(self.operator, False)


class ReflexActivation(IdentifiedModel):
    """A record that a reflex rule fired, and what it added.

    The unique constraint on (order, rule) is what makes reflex testing safe to
    re-run: correcting a result re-evaluates every rule, and without it a
    corrected TSH would add a second free T4 each time somebody fixed a typo.
    """

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        ORDERED = "Ordered", "Ordered"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"

    order = models.ForeignKey(
        "laboratory.Order", on_delete=models.CASCADE, related_name="reflex_activations"
    )
    rule = models.ForeignKey(ReflexRule, on_delete=models.CASCADE, related_name="activations")
    #: The value that triggered it, as text and as it stood. If the result is
    #: later corrected, this still shows why the extra test was added — which
    #: is the question asked when somebody queries the bill.
    trigger_value = models.CharField(max_length=64)
    new_test = models.ForeignKey(
        "laboratory.TestDefinition", on_delete=models.CASCADE, related_name="reflex_activations"
    )
    triggered_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)

    class Meta:
        db_table = "reflex_activations"
        ordering = ["-triggered_at"]
        constraints = [
            models.UniqueConstraint(fields=["order", "rule"], name="reflex_activation_unique")
        ]

    def __str__(self) -> str:
        return f"{self.rule_id} → {self.new_test_id} on {self.order_id}"


class DemographicReferenceRange(IdentifiedModel, ActivatableModel):
    """Age, sex and pregnancy specific reference intervals.

    A single interval per analyte is wrong for most of chemistry and
    haematology. Creatinine in a six-year-old, haemoglobin in a menstruating
    woman and alkaline phosphatase in a growing adolescent all have intervals
    that differ from the adult default by more than the flag threshold — so a
    catalogue-only interval flags healthy children and misses sick ones.

    Several rows can match one patient. ``specificity`` decides which wins; see
    ``apps.clinical.services.find_reference_range``, which takes the
    highest-scoring match rather than the first.

    A null bound means *unbounded on that side*, not zero. An analyte with only
    an upper limit leaves ``low_normal`` null.
    """

    class GenderScope(models.TextChoices):
        ALL = "All", "All"
        MALE = "M", "Male"
        FEMALE = "F", "Female"

    test = models.ForeignKey(
        "laboratory.TestDefinition", on_delete=models.CASCADE, related_name="demographic_ranges"
    )
    test_code = models.CharField(max_length=64)
    age_min = models.IntegerField(null=True, blank=True, help_text="Inclusive lower bound in years")
    age_max = models.IntegerField(null=True, blank=True, help_text="Inclusive upper bound in years")
    gender = models.CharField(max_length=8, choices=GenderScope.choices, default=GenderScope.ALL)
    pregnancy = models.BooleanField(default=False)
    trimester = models.PositiveSmallIntegerField(null=True, blank=True)
    #: Null means unbounded on that side, not zero.
    low_normal = models.FloatField(null=True, blank=True)
    high_normal = models.FloatField(null=True, blank=True)
    #: Demographic critical limits override the catalogue's, because a panic
    #: potassium in a neonate is not the adult number.
    low_critical = models.FloatField(null=True, blank=True)
    high_critical = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=64, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "demographic_reference_ranges"
        ordering = ["test_code", "age_min"]
        indexes = [models.Index(fields=["test", "active"])]

    def __str__(self) -> str:
        return f"{self.test_code} {self.gender} {self.age_min}–{self.age_max}"

    @property
    def specificity(self) -> int:
        """How narrowly this interval is targeted; higher wins when several match.

        The weights encode a clinical ordering, not an arbitrary one: pregnancy
        outranks age and sex because a pregnancy-specific interval already
        implies both, and a trimester-specific one is narrower still. Two
        intervals scoring equally means the configuration is ambiguous, and the
        integrity check reports overlapping bands.
        """
        score = 0
        if self.age_min is not None or self.age_max is not None:
            score += 2
        if self.gender != self.GenderScope.ALL:
            score += 2
        if self.pregnancy:
            score += 3
            if self.trimester:
                score += 2
        return score

    def applies_to(self, *, age_years, gender, is_pregnant=False, trimester=None) -> bool:
        """Whether this interval is valid for the given demographics.

        A range scoped to an age band or a sex is only used when that
        information is actually known — an unknown age must not silently pick
        up a paediatric interval.
        """
        if self.age_min is not None or self.age_max is not None:
            if age_years is None:
                return False
            if self.age_min is not None and age_years < self.age_min:
                return False
            if self.age_max is not None and age_years > self.age_max:
                return False

        if self.gender != self.GenderScope.ALL:
            if not gender or gender != self.gender:
                return False

        if self.pregnancy and not is_pregnant:
            return False
        if self.pregnancy and self.trimester and trimester != self.trimester:
            return False

        return True


class CalculatedTest(IdentifiedModel, ActivatableModel):
    """A test whose value is derived from other results rather than measured.

    The formula is a *choice*, not an expression: each one is implemented in
    ``apps.clinical.services.compute_calculated_test`` with its own validity
    conditions, which a general expression evaluator could not express. The
    Friedewald equation, for instance, is invalid above 4.5 mmol/L
    triglycerides and returns nothing rather than a wrong LDL — that rule lives
    in the code because getting it wrong produces a plausible number.

    ``inputs`` lists the test codes the formula needs. All must be present on
    the order; a partial set yields no result rather than a guess.
    """

    class Formula(models.TextChoices):
        LDL_FRIEDEWALD = "ldl_friedewald", "LDL (Friedewald)"
        ANION_GAP = "anion_gap", "Anion gap"
        AG_RATIO = "a_g_ratio", "Albumin/globulin ratio"
        EGFR_CKD_EPI = "egfr_ckd_epi", "eGFR (CKD-EPI 2021)"
        CORRECTED_CALCIUM = "corrected_calcium", "Albumin-corrected calcium"
        OSMOLALITY = "osmolality", "Calculated osmolality"
        TRANSFERRIN_SATURATION = "transferrin_saturation", "Transferrin saturation"

    test_code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    formula = models.CharField(max_length=64, choices=Formula.choices)
    inputs = models.JSONField(default=list, blank=True, help_text="Required input test codes")
    unit = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "calculated_tests"
        ordering = ["test_code"]

    def __str__(self) -> str:
        return f"{self.test_code} — {self.name}"


class NotifiableCondition(IdentifiedModel, ActivatableModel):
    """A condition that must be reported to public health authorities.

    Detection is by *test*, not by result value: any result for a linked test
    raises a notification for a person to review. That is deliberately
    over-inclusive — a false notification is reviewed and closed in seconds,
    a missed one is a statutory breach and, for something like a meningococcus,
    a delayed public health response.

    Dx detects and tracks; it does not transmit. Electronic laboratory
    reporting to a health authority is a separate piece of work — see
    docs/ROADMAP.md §9.
    """

    name = models.CharField(max_length=255)
    organism = models.CharField(max_length=255, null=True, blank=True)
    tests = models.ManyToManyField(
        "laboratory.TestDefinition", blank=True, related_name="notifiable_conditions"
    )
    reporting_body = models.CharField(max_length=255)
    timeframe = models.CharField(max_length=32, default="24h", help_text="Label shown to users, e.g. 24h or 7d")
    timeframe_hours = models.PositiveIntegerField(
        default=24,
        help_text="The statutory window in hours. Kept alongside the label so "
                  "overdue notifications can be found in SQL instead of by "
                  "parsing the label on every row.",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notifiable_conditions"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def parse_timeframe(label: str) -> int:
        """Convert a label such as '24h' or '7d' into hours."""
        raw = (label or "24h").strip().lower()
        try:
            value = int(raw.rstrip("hd"))
        except ValueError:
            return 24
        return value * 24 if raw.endswith("d") else value

    def save(self, *args, **kwargs):
        # Keep the numeric window in step with the label people edit, so the
        # overdue query stays a SQL comparison rather than a parse per row.
        self.timeframe_hours = self.parse_timeframe(self.timeframe)
        super().save(*args, **kwargs)


class EpidemiologyNotificationQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status__in=[
            EpidemiologyNotification.Status.SUBMITTED,
            EpidemiologyNotification.Status.CLOSED,
        ])

    def overdue(self):
        """Notifications past their statutory reporting window.

        Must agree with ``EpidemiologyNotification.is_overdue``, which answers
        the same question for a single instance.
        """
        from django.db.models import DateTimeField, ExpressionWrapper, F
        from datetime import timedelta

        # `timedelta(hours=1) * F(...)` is how a database-side interval
        # multiplication is expressed in the ORM: a Python timedelta cannot be
        # built from a column value, so the unit is multiplied by the column.
        deadline = ExpressionWrapper(
            F("detected_at") + timedelta(hours=1) * F("condition__timeframe_hours"),
            output_field=DateTimeField(),
        )
        return self.open().annotate(_deadline=deadline).filter(_deadline__lt=timezone.now())


class EpidemiologyNotification(IdentifiedModel):
    """One notifiable condition detected on one order, and its onward journey.

    The unique constraint on (order, condition) makes detection idempotent:
    correcting a result re-runs the engine, and without it every correction
    would raise a duplicate notification for the same organism.

    ``reference_number`` is filled in by hand after submitting to the
    authority, because submission is currently a person using the authority's
    own portal. It is the evidence that the statutory duty was discharged, so
    the record is not closed without it.
    """

    class Status(models.TextChoices):
        # Pending → Reviewed → Submitted → Closed. Only a person moves it past
        # Reviewed; nothing here transmits to an authority automatically.
        PENDING = "Pending", "Pending review"
        REVIEWED = "Reviewed", "Reviewed"
        SUBMITTED = "Submitted", "Submitted"
        CLOSED = "Closed", "Closed"

    order = models.ForeignKey(
        "laboratory.Order", on_delete=models.CASCADE, related_name="epidemiology_notifications"
    )
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="epidemiology_notifications"
    )
    condition = models.ForeignKey(
        NotifiableCondition, on_delete=models.CASCADE, related_name="notifications"
    )
    #: The statutory clock runs from detection, not from review. A laboratory
    #: cannot extend its own reporting window by being slow to look.
    detected_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.CharField(max_length=150, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.CharField(max_length=150, null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reference_number = models.CharField(
        max_length=64, null=True, blank=True, help_text="Reference issued by the receiving authority"
    )
    notes = models.TextField(null=True, blank=True)

    objects = EpidemiologyNotificationQuerySet.as_manager()

    class Meta:
        db_table = "epidemiology_notifications"
        ordering = ["-detected_at"]
        constraints = [
            models.UniqueConstraint(fields=["order", "condition"], name="epi_notification_unique")
        ]

    def __str__(self) -> str:
        return f"{self.condition_id} for {self.patient_id}"

    @property
    def is_overdue(self) -> bool:
        """Whether the statutory reporting window has elapsed.

        Mirrors ``EpidemiologyNotificationQuerySet.overdue``; change both
        together.
        """
        if self.status in {self.Status.SUBMITTED, self.Status.CLOSED}:
            return False
        hours = self.condition.timeframe_hours or 24
        return (timezone.now() - self.detected_at).total_seconds() / 3600 > hours
