"""Core laboratory workflow: test catalogue, orders, specimens and results."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.constants import OrderStatus, Priority, ResultFlag
from apps.common.models import ActivatableModel, IdentifiedModel


class TestDefinition(IdentifiedModel, ActivatableModel):
    """The test catalogue entry — analyte, units and reference ranges.

    The single most consequential table in the system: it decides what can be
    ordered, what a result means, and when somebody is telephoned. Editing a
    row here changes the interpretation of every result produced afterwards,
    which is why `check_workflows` reports results whose stored flags no longer
    agree with the current interval.

    Catalogue entries are **deactivated, never deleted** (`ActivatableModel`).
    Results reference their test, and a report from 2026 must still resolve its
    analyte name in 2031.
    """

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="tests"
    )
    units = models.CharField(max_length=64, null=True, blank=True)
    tat_hours = models.FloatField("turnaround target (hours)", null=True, blank=True)
    #: JSON rather than four columns because the legacy Drizzle schema stored
    #: it that way and several key spellings are in the wild — see
    #: ``_range_value``, which accepts all of them. New rows should use the
    #: canonical keys.
    #:
    #: Any key may be absent, meaning *unbounded on that side*, not zero. A
    #: one-sided interval is normal: most tumour markers have only an upper
    #: limit.
    reference_range = models.JSONField(
        null=True,
        blank=True,
        help_text="Canonical shape: {min, max, panicLow, panicHigh}",
    )
    specimen_types = models.JSONField(default=list, blank=True)
    methodology = models.CharField(max_length=255, null=True, blank=True)
    loinc_code = models.CharField(max_length=32, null=True, blank=True)
    auto_verify_permitted = models.BooleanField(
        default=False,
        help_text=(
            "Allow decision rules to release results for this analyte without a "
            "person reading them. Off until the laboratory has validated "
            "autoverification for this test specifically — it is an "
            "analyte-scoped decision, not a system-wide mode."
        ),
    )

    class Meta:
        db_table = "test_definitions"
        ordering = ["code"]
        indexes = [models.Index(fields=["department", "active"])]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    # ── Reference range helpers ──────────────────────────────────────────────

    def _range_value(self, *keys: str) -> float | None:
        """First of ``keys`` present in the stored interval, as a float.

        Several spellings survive from the legacy schema (``min``/``low``/
        ``lowNormal``), so each accessor lists its synonyms in preference
        order. A non-numeric value is treated as absent rather than raising:
        a mistyped catalogue entry must not break result entry for every
        patient on the bench.
        """
        data = self.reference_range or {}
        for key in keys:
            value = data.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None

    @property
    def normal_low(self) -> float | None:
        return self._range_value("min", "low", "lowNormal")

    @property
    def normal_high(self) -> float | None:
        return self._range_value("max", "high", "highNormal")

    @property
    def panic_low(self) -> float | None:
        return self._range_value("panicLow", "criticalLow", "lowCritical")

    @property
    def panic_high(self) -> float | None:
        return self._range_value("panicHigh", "criticalHigh", "highCritical")

    @property
    def reference_display(self) -> str:
        low, high = self.normal_low, self.normal_high
        if low is not None and high is not None:
            return f"{low:g} – {high:g}"
        if high is not None:
            return f"< {high:g}"
        if low is not None:
            return f"> {low:g}"
        return "—"

    def evaluate(self, value) -> str:
        """Classify a numeric result against this test's reference range.

        Critical limits are checked **before** the reference interval, so a
        result outside both is reported as critical rather than merely high —
        the order matters and reversing it would silently downgrade panic
        values.

        A one-sided range (only a lower or only an upper bound) is honoured.
        The legacy helper treated a missing bound as "no opinion" and returned
        Normal, so every tumour marker came back unflagged.

        A non-numeric value returns Normal rather than raising: qualitative
        results ("Not detected") legitimately reach here.
        """
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return ResultFlag.NORMAL

        panic_low, panic_high = self.panic_low, self.panic_high
        if panic_low is not None and numeric < panic_low:
            return ResultFlag.CRITICAL_LOW
        if panic_high is not None and numeric > panic_high:
            return ResultFlag.CRITICAL_HIGH

        low, high = self.normal_low, self.normal_high
        if low is not None and numeric < low:
            return ResultFlag.LOW
        if high is not None and numeric > high:
            return ResultFlag.HIGH
        return ResultFlag.NORMAL


class AuthorizationQueue(IdentifiedModel):
    """Work queue segregating results awaiting authorisation."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="queues"
    )
    allowed_roles = models.JSONField(default=list, blank=True)
    created_by = models.CharField(max_length=150, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "authorization_queues"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def permits(self, user) -> bool:
        roles = self.allowed_roles or []
        return not roles or user.role in roles


class OrderQuerySet(models.QuerySet):
    def pending(self):
        return self.exclude(status__in=[OrderStatus.COMPLETED, OrderStatus.CANCELLED, OrderStatus.REJECTED])

    def completed(self):
        return self.filter(status=OrderStatus.COMPLETED)

    def for_patient(self, patient_id: str):
        return self.filter(patient_id=patient_id)


class Order(IdentifiedModel):
    """A test request for one patient, identified by its accession number.

    The accession number is the laboratory's own identifier and is what appears
    on the tube, the worklist and every analyser exchange. It is allocated
    under a PostgreSQL advisory lock held for the calling transaction (see
    ``apps.laboratory.services.generate_accession_number``) because two
    concurrent requests previously received the same number.

    Status is a single field rather than a state machine, and transitions are
    enforced in the service layer. Anything reading status directly should
    treat these as ordered: Pending → Received → In Progress → Resulted →
    Technically Validated → Clinically Verified → Completed, with Rejected and
    Cancelled as terminal side exits.
    """

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="orders")
    accession_number = models.CharField(max_length=32, unique=True)
    status = models.CharField(max_length=48, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    order_by = models.CharField(max_length=255, null=True, blank=True)
    requester = models.ForeignKey(
        "reporting.Requester", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    timestamp = models.DateTimeField(default=timezone.now, help_text="Order creation time")
    queue = models.ForeignKey(
        AuthorizationQueue, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    priority = models.CharField(max_length=32, choices=Priority.choices, default=Priority.ROUTINE)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    tests = models.ManyToManyField(TestDefinition, related_name="orders", blank=True)

    #: The ordering system's own identifier for this request (HL7 ORC-2).
    #: Kept so a later cancellation or query finds the order we made, and so a
    #: retransmitted order is recognised rather than accessioned twice.
    placer_order_number = models.CharField(max_length=64, blank=True, default="")
    source_message_id = models.CharField(
        max_length=64, blank=True, default="",
        help_text="Control id of the inbound message that created this order.",
    )

    objects = OrderQuerySet.as_manager()

    class Meta:
        db_table = "orders"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["patient", "-timestamp"]),
            models.Index(fields=["accession_number"]),
            models.Index(fields=["placer_order_number"]),
        ]

    def __str__(self) -> str:
        return self.accession_number

    @property
    def is_complete(self) -> bool:
        return self.status == OrderStatus.COMPLETED

    @property
    def turnaround_hours(self) -> float | None:
        """Elapsed hours from order to completion, or to now if still open.

        Measured from the order timestamp, not from specimen receipt, so it is
        the interval the requesting clinician actually experiences. An open
        order keeps growing, which is what makes a breach visible before it is
        finished rather than after.
        """
        end = self.completed_at or timezone.now()
        if not self.timestamp:
            return None
        return (end - self.timestamp).total_seconds() / 3600.0


class Specimen(IdentifiedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="specimens")
    type = models.CharField(max_length=128)
    container_id = models.CharField(max_length=128, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    collection_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "specimens"
        ordering = ["-collection_date"]
        indexes = [models.Index(fields=["order"]), models.Index(fields=["container_id"])]

    def __str__(self) -> str:
        return f"{self.type} — {self.container_id or self.id}"


class Result(IdentifiedModel):
    """One analyte result for one order.

    ``REPORT_TEST_ID`` is a reserved pseudo test used to carry report-level
    narrative comments, preserved from the legacy data model. Rows with that
    key have no analyte, no numeric value and no verifier, so **anything
    iterating results must skip them** — ``is_report_row`` exists for exactly
    that, and forgetting it is the most common bug in this area.

    ``value`` is the authoritative text; ``numeric_value`` is a shadow column
    kept in step by ``save``. Delta checks, trending and every decision rule
    read the shadow, so a write that bypasses ``save()`` — ``bulk_create``,
    ``QuerySet.update`` — leaves them blind to the result. `check_workflows`
    reports that specific drift.
    """

    REPORT_TEST_ID = "REPORT"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="results")
    test = models.ForeignKey(
        TestDefinition, null=True, blank=True, on_delete=models.PROTECT, related_name="results"
    )
    test_key = models.CharField(
        max_length=64,
        help_text="Test id, or the reserved value REPORT for narrative rows",
    )
    value = models.TextField(null=True, blank=True)
    numeric_value = models.FloatField(
        null=True, blank=True, help_text="Populated when the result parses as a number"
    )
    result_flags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=48, choices=OrderStatus.choices, default=OrderStatus.RESULTED)
    entered_by = models.CharField(max_length=150, null=True, blank=True)
    technical_validated_by = models.CharField(max_length=150, null=True, blank=True)
    clinical_verified_by = models.CharField(max_length=150, null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "results"
        ordering = ["test_key"]
        constraints = [
            models.UniqueConstraint(fields=["order", "test_key"], name="results_order_test_unique"),
        ]
        indexes = [models.Index(fields=["order"]), models.Index(fields=["test", "-timestamp"])]

    def __str__(self) -> str:
        return f"{self.order_id}/{self.test_key} = {self.value}"

    @property
    def is_report_row(self) -> bool:
        return self.test_key == self.REPORT_TEST_ID

    def save(self, *args, **kwargs):
        # Keep the numeric shadow column in step with the stored text value so
        # trending and delta checks never have to re-parse strings.
        #
        # Deliberately unconditional: a corrected result that becomes
        # non-numeric ("haemolysed" replacing 6.9) must clear the shadow, or
        # the old number goes on driving deltas for a value nobody reported.
        if self.value is None or self.value == "":
            self.numeric_value = None
        else:
            try:
                self.numeric_value = float(self.value)
            except (TypeError, ValueError):
                self.numeric_value = None
        super().save(*args, **kwargs)

    def recompute_flags(self) -> list[str]:
        """Re-derive this result's flags from the catalogue interval.

        Does **not** save — the caller decides, because flags are usually
        computed inside a larger transaction that also writes the value.

        Only catalogue limits are applied here; the demographic interval is
        applied by the clinical engine, which has the patient in scope. A
        result with no test or no numeric value has no flags rather than an
        empty-string flag.
        """
        if self.test is None or self.numeric_value is None:
            return []
        flag = self.test.evaluate(self.numeric_value)
        self.result_flags = [] if flag == ResultFlag.NORMAL else [flag]
        return self.result_flags


class ResultSignature(IdentifiedModel):
    """Electronic signature captured at technical or clinical validation.

    Distinct from :class:`apps.compliance.models.ElectronicSignature`, and both
    are written. This one is the laboratory-facing record printed on the
    report's signature manifest; that one is the Part 11 record binding the
    signature to a content hash and an audit sequence. Keeping them separate
    means a change to report layout cannot disturb the regulatory record.
    """

    class SignatureType(models.TextChoices):
        TECHNICAL = "technical", "Technical"
        CLINICAL = "clinical", "Clinical"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="signatures")
    signed_by = models.CharField(max_length=255)
    signed_at = models.DateTimeField(default=timezone.now)
    signature_type = models.CharField(max_length=32, choices=SignatureType.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "result_signatures"
        ordering = ["-signed_at"]

    def __str__(self) -> str:
        return f"{self.signature_type} by {self.signed_by}"


class SpecimenReceiving(IdentifiedModel):
    """Sample reception, condition assessment and rejection.

    The pre-analytical gate, and where most laboratory errors are actually
    caught. ``condition`` is an assessment of the sample; ``status`` is the
    decision taken about it. They are separate because a marginal sample is
    frequently still run, with the condition noted on the report — and
    autoverification refuses anything not received as Acceptable.

    A rejection requires a ``rejection_reason`` so the requester can be told
    what to recollect; "rejected" with no reason produces a second useless
    sample.
    """

    class Condition(models.TextChoices):
        ACCEPTABLE = "Acceptable", "Acceptable"
        MARGINAL = "Marginal", "Marginal"
        REJECTED = "Rejected", "Rejected"

    class Status(models.TextChoices):
        ACCEPTED = "Accepted", "Accepted"
        REJECTED = "Rejected", "Rejected"
        RECOLLECTION_REQUIRED = "Recollection-Required", "Recollection required"

    specimen = models.ForeignKey(Specimen, on_delete=models.CASCADE, related_name="receipts")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="receipts")
    received_at = models.DateTimeField(default=timezone.now)
    received_by = models.CharField(max_length=150)
    condition = models.CharField(max_length=32, choices=Condition.choices, default=Condition.ACCEPTABLE)
    condition_notes = models.TextField(null=True, blank=True)
    rejection_reason = models.ForeignKey(
        "quality.RejectionCriterion", null=True, blank=True, on_delete=models.SET_NULL, related_name="receipts"
    )
    temperature = models.CharField(max_length=64, null=True, blank=True)
    volume = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACCEPTED)

    class Meta:
        db_table = "specimen_receiving"
        ordering = ["-received_at"]

    def __str__(self) -> str:
        return f"{self.specimen_id} — {self.status}"


class PhlebotomySchedule(IdentifiedModel):
    class CollectionType(models.TextChoices):
        ROUTINE = "Routine", "Routine"
        STAT = "STAT", "STAT"
        TIMED = "Timed", "Timed"

    class Status(models.TextChoices):
        SCHEDULED = "Scheduled", "Scheduled"
        IN_PROGRESS = "InProgress", "In progress"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"

    patient = models.ForeignKey("patients.Patient", on_delete=models.CASCADE, related_name="phlebotomy_rounds")
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="phlebotomy_rounds")
    ward_location = models.CharField(max_length=255)
    scheduled_at = models.DateTimeField()
    collection_type = models.CharField(
        max_length=32, choices=CollectionType.choices, default=CollectionType.ROUTINE
    )
    tests = models.ManyToManyField(TestDefinition, blank=True, related_name="phlebotomy_rounds")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="phlebotomy_rounds"
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.SCHEDULED)
    notes = models.TextField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "phlebotomy_schedules"
        ordering = ["scheduled_at"]
        indexes = [models.Index(fields=["status", "scheduled_at"])]

    def __str__(self) -> str:
        return f"{self.patient_id} @ {self.ward_location}"


class RetentionPolicy(IdentifiedModel, ActivatableModel):
    specimen_type = models.CharField(max_length=128)
    retention_days = models.PositiveIntegerField()
    temperature = models.CharField(max_length=64, null=True, blank=True)
    disposal_method = models.CharField(max_length=128, default="Biohazard Disposal")
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "retention_policies"
        ordering = ["specimen_type"]

    def __str__(self) -> str:
        return f"{self.specimen_type} — {self.retention_days}d"


class SpecimenDisposal(IdentifiedModel):
    specimen = models.ForeignKey(Specimen, on_delete=models.CASCADE, related_name="disposals")
    policy = models.ForeignKey(
        RetentionPolicy, null=True, blank=True, on_delete=models.SET_NULL, related_name="disposals"
    )
    disposed_at = models.DateTimeField(default=timezone.now)
    disposed_by = models.CharField(max_length=150)
    batch_number = models.CharField(max_length=64, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "specimen_disposals"
        ordering = ["-disposed_at"]

    def __str__(self) -> str:
        return f"{self.specimen_id} disposed {self.disposed_at:%Y-%m-%d}"


class OrderDiagnosis(IdentifiedModel):
    """An ICD-10 diagnosis attached to an order.

    Ranked, because the first-listed code is the primary indication and that
    distinction is what a payer reads. ``code_value`` and ``description`` are
    denormalised deliberately: a diagnosis recorded against a specimen in 2026
    must still read correctly in 2031 after the catalogue row has been
    superseded, revised or withdrawn. The foreign key is for lookup; the copy
    is the record.
    """

    class Kind(models.TextChoices):
        WORKING = "working", "Working / provisional"
        CONFIRMED = "confirmed", "Confirmed"
        RULE_OUT = "rule_out", "Rule out"
        HISTORY = "history", "Relevant history"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="diagnoses")
    code = models.ForeignKey(
        "interop.Icd10Code", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="order_diagnoses",
    )
    code_value = models.CharField(max_length=16)
    description = models.TextField(blank=True)
    rank = models.PositiveSmallIntegerField(
        default=1, help_text="1 is the primary indication."
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.WORKING)
    recorded_by = models.CharField(max_length=150, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "order_diagnoses"
        ordering = ["rank", "code_value"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "code_value"], name="order_diagnosis_unique"
            ),
        ]
        indexes = [models.Index(fields=["code_value"])]

    def __str__(self) -> str:
        return f"{self.code_value} on {self.order_id}"

    @property
    def is_primary(self) -> bool:
        return self.rank == 1
