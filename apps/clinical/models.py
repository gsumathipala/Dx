"""The clinical decision engine: delta checks, critical values, reflex testing,
demographic reference intervals, calculated tests and notifiable conditions."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import ActivatableModel, IdentifiedModel


class DeltaCheckRule(IdentifiedModel):
    class DeltaType(models.TextChoices):
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
    threshold = models.FloatField()
    direction = models.CharField(max_length=16, choices=Direction.choices, default=Direction.ANY)
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
    test_code = models.CharField(max_length=64)
    value = models.CharField(max_length=64)
    threshold = models.CharField(max_length=64)
    critical_type = models.CharField(max_length=8, choices=CriticalType.choices)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=150, null=True, blank=True)
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
    """Documented read-back of a critical value."""

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
        comparisons = {
            self.Operator.GT: value > self.threshold,
            self.Operator.GTE: value >= self.threshold,
            self.Operator.LT: value < self.threshold,
            self.Operator.LTE: value <= self.threshold,
            self.Operator.EQ: value == self.threshold,
        }
        return comparisons.get(self.operator, False)


class ReflexActivation(IdentifiedModel):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        ORDERED = "Ordered", "Ordered"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"

    order = models.ForeignKey(
        "laboratory.Order", on_delete=models.CASCADE, related_name="reflex_activations"
    )
    rule = models.ForeignKey(ReflexRule, on_delete=models.CASCADE, related_name="activations")
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
    """Age, sex and pregnancy specific reference intervals."""

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
    low_normal = models.FloatField(null=True, blank=True)
    high_normal = models.FloatField(null=True, blank=True)
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
        """How narrowly this interval is targeted; higher wins when several match."""
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
    """A test whose value is derived from other results rather than measured."""

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
    """A condition that must be reported to public health authorities."""

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

        deadline = ExpressionWrapper(
            F("detected_at") + timedelta(hours=1) * F("condition__timeframe_hours"),
            output_field=DateTimeField(),
        )
        return self.open().annotate(_deadline=deadline).filter(_deadline__lt=timezone.now())


class EpidemiologyNotification(IdentifiedModel):
    class Status(models.TextChoices):
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
