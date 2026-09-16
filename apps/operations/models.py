"""Laboratory operations: worksheets, workstations, routing, TAT, alerts,
messaging, storage and system settings."""
from __future__ import annotations

from django.conf import settings as django_settings
from django.db import models
from django.utils import timezone

from apps.common.constants import Priority
from apps.common.models import ActivatableModel, IdentifiedModel


class SystemSetting(IdentifiedModel):
    """Key/value configuration store carried over from the legacy schema."""

    key = models.CharField(max_length=128, unique=True)
    value = models.JSONField(null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "settings"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key

    @classmethod
    def get(cls, key: str, default=None):
        row = cls.objects.filter(key=key).values("value").first()
        return row["value"] if row else default

    @classmethod
    def set(cls, key: str, value, description: str | None = None):
        obj, _ = cls.objects.update_or_create(
            key=key, defaults={"value": value, "description": description}
        )
        return obj


class SystemAlert(IdentifiedModel, ActivatableModel):
    class Kind(models.TextChoices):
        INFO = "info", "Information"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Critical"

    message = models.TextField()
    type = models.CharField(max_length=16, choices=Kind.choices, default=Kind.INFO)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    read_by = models.ManyToManyField(
        django_settings.AUTH_USER_MODEL, blank=True, related_name="read_alerts"
    )

    class Meta:
        db_table = "system_alerts"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.type}] {self.message[:60]}"

    @property
    def is_current(self) -> bool:
        return self.active and (self.expires_at is None or self.expires_at > timezone.now())


class Message(IdentifiedModel):
    """Internal messaging between laboratory staff."""

    sender = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
        related_name="sent_messages", help_text="Null when the sender is not a person.",
    )
    sender_label = models.CharField(
        max_length=255, blank=True,
        help_text="Who sent it when no user did — a decision rule, or the system.",
    )
    recipient = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
        related_name="received_messages", help_text="Null for a broadcast",
    )
    recipient_department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="messages",
    )
    subject = models.CharField(max_length=255)
    body = models.TextField()
    read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(default=timezone.now)
    related_entity_type = models.CharField(max_length=64, null=True, blank=True)
    related_entity_id = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "messages"
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["recipient", "read", "-timestamp"])]

    def __str__(self) -> str:
        return self.subject

    @property
    def from_display(self) -> str:
        """Who the message is from, human or not.

        A rule-generated message must not appear to come from whoever happened
        to be logged in when it fired.
        """
        if self.sender_id:
            return self.sender.get_full_name() or self.sender.username
        return self.sender_label or "System"


class Feedback(IdentifiedModel):
    class Kind(models.TextChoices):
        BUG = "Bug", "Bug"
        FEATURE = "Feature", "Feature request"
        GENERAL = "General", "General"

    class Status(models.TextChoices):
        NEW = "New", "New"
        REVIEWED = "Reviewed", "Reviewed"
        CLOSED = "Closed", "Closed"

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedback"
    )
    type = models.CharField(max_length=16, choices=Kind.choices, default=Kind.GENERAL)
    message = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "feedback"
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.type} from {self.user_id}"


class Worksheet(IdentifiedModel):
    class Status(models.TextChoices):
        DRAFT = "Draft", "Draft"
        ACTIVE = "Active", "Active"
        COMPLETED = "Completed", "Completed"

    name = models.CharField(max_length=255)
    department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="worksheets",
    )
    tests = models.ManyToManyField("laboratory.TestDefinition", blank=True, related_name="worksheets")
    orders = models.ManyToManyField("laboratory.Order", blank=True, related_name="worksheets")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = "worksheets"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Workstation(IdentifiedModel, ActivatableModel):
    class Status(models.TextChoices):
        ONLINE = "Online", "Online"
        OFFLINE = "Offline", "Offline"
        MAINTENANCE = "Maintenance", "Maintenance"

    name = models.CharField(max_length=255)
    department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="workstations",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    printer_id = models.CharField(max_length=64, null=True, blank=True)
    instruments = models.ManyToManyField(
        "quality.Equipment", blank=True, related_name="workstations"
    )
    supported_tests = models.ManyToManyField(
        "laboratory.TestDefinition", blank=True, related_name="workstations"
    )
    supported_specimen_types = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ONLINE)
    max_throughput = models.PositiveIntegerField(
        default=100, help_text="Tests per hour, used for load balancing"
    )

    class Meta:
        db_table = "workstations"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def queued_tests(self) -> int:
        return self.assignments.filter(status=RoutingAssignment.Status.PENDING).count()

    @property
    def current_tests(self) -> int:
        return self.assignments.filter(status=RoutingAssignment.Status.IN_PROGRESS).count()

    @property
    def utilisation(self) -> float:
        if not self.max_throughput:
            return 1.0
        return self.current_tests / self.max_throughput

    def can_accept(self, test=None, specimen_type: str | None = None) -> bool:
        if not self.active or self.status != self.Status.ONLINE:
            return False
        if test is not None and not self.supported_tests.filter(pk=test.pk).exists():
            return False
        if specimen_type and self.supported_specimen_types:
            if specimen_type not in self.supported_specimen_types:
                return False
        return True


class RoutingRule(IdentifiedModel, ActivatableModel):
    test = models.ForeignKey(
        "laboratory.TestDefinition", on_delete=models.CASCADE, related_name="routing_rules"
    )
    workstations = models.ManyToManyField(
        Workstation, blank=True, related_name="routing_rules",
        help_text="Preferred workstations, highest priority first",
    )
    department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="routing_rules",
    )
    specimen_type = models.CharField(max_length=128, null=True, blank=True)
    conditions = models.JSONField(default=dict, blank=True)
    priority = models.IntegerField(default=0)

    class Meta:
        db_table = "routing_rules"
        ordering = ["-priority"]

    def __str__(self) -> str:
        return f"route {self.test_id}"


class RoutingAssignment(IdentifiedModel):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        IN_PROGRESS = "In Progress", "In progress"
        COMPLETED = "Completed", "Completed"
        FAILED = "Failed", "Failed"

    order = models.ForeignKey("laboratory.Order", on_delete=models.CASCADE, related_name="routing")
    test = models.ForeignKey(
        "laboratory.TestDefinition", on_delete=models.CASCADE, related_name="routing_assignments"
    )
    workstation = models.ForeignKey(Workstation, on_delete=models.CASCADE, related_name="assignments")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    timestamp = models.DateTimeField(default=timezone.now)
    estimated_completion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "routing_assignments"
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["workstation", "status"])]

    def __str__(self) -> str:
        return f"{self.test_id} → {self.workstation_id}"


class TatThreshold(IdentifiedModel, ActivatableModel):
    """Turnaround time targets by test, department or globally."""

    class Scope(models.TextChoices):
        TEST = "test", "Test"
        DEPARTMENT = "department", "Department"
        GLOBAL = "global", "Global"

    scope = models.CharField(max_length=16, choices=Scope.choices)
    test = models.ForeignKey(
        "laboratory.TestDefinition", null=True, blank=True, on_delete=models.CASCADE,
        related_name="tat_thresholds",
    )
    department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.CASCADE,
        related_name="tat_thresholds",
    )
    target_hours = models.FloatField()
    warning_hours = models.FloatField()
    breach_hours = models.FloatField()
    priority = models.CharField(max_length=32, choices=Priority.choices, default=Priority.ROUTINE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "tat_thresholds"
        ordering = ["scope"]

    def __str__(self) -> str:
        target = self.test_id or self.department_id or "global"
        return f"TAT {target} @ {self.target_hours}h"


class TatBreach(IdentifiedModel):
    class BreachType(models.TextChoices):
        WARNING = "warning", "Approaching target"
        CRITICAL = "critical", "Target breached"

    order = models.ForeignKey("laboratory.Order", on_delete=models.CASCADE, related_name="tat_breaches")
    actual_hours = models.FloatField()
    target_hours = models.FloatField()
    breach_type = models.CharField(max_length=16, choices=BreachType.choices)
    detected_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tat_breaches"
        ordering = ["-detected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "breach_type"], name="tat_breach_unique_per_type"
            )
        ]

    def __str__(self) -> str:
        return f"{self.order_id} {self.breach_type} ({self.actual_hours:.1f}h)"


class StorageLocation(IdentifiedModel, ActivatableModel):
    """Freezer, rack, box and position hierarchy for specimen storage."""

    class Kind(models.TextChoices):
        FREEZER = "freezer", "Freezer"
        FRIDGE = "fridge", "Refrigerator"
        RACK = "rack", "Rack"
        BOX = "box", "Box"
        SHELF = "shelf", "Shelf"
        ROOM = "room", "Room"

    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    temperature = models.CharField(max_length=32, null=True, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    rows = models.PositiveSmallIntegerField(null=True, blank=True)
    columns = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "storage_locations"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def path(self) -> str:
        parts, node = [], self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return " / ".join(reversed(parts))

    @property
    def occupancy(self) -> int:
        return self.stored_specimens.filter(removed_at__isnull=True).count()

    @property
    def is_full(self) -> bool:
        return bool(self.capacity and self.occupancy >= self.capacity)


class StorageAssignment(IdentifiedModel):
    """Where a specimen physically sits, and its movement history."""

    specimen = models.ForeignKey(
        "laboratory.Specimen", on_delete=models.CASCADE, related_name="storage_assignments"
    )
    location = models.ForeignKey(
        StorageLocation, on_delete=models.PROTECT, related_name="stored_specimens"
    )
    position = models.CharField(max_length=32, null=True, blank=True, help_text="e.g. A3")
    stored_at = models.DateTimeField(default=timezone.now)
    stored_by = models.CharField(max_length=150)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = "storage_assignments"
        ordering = ["-stored_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["location", "position"],
                condition=models.Q(removed_at__isnull=True),
                name="storage_position_occupied_once",
            )
        ]

    def __str__(self) -> str:
        return f"{self.specimen_id} @ {self.location_id}/{self.position or '-'}"

    @property
    def is_current(self) -> bool:
        return self.removed_at is None


class ChainOfCustodyEvent(IdentifiedModel):
    """Specimen custody transfer record."""

    class EventType(models.TextChoices):
        COLLECTED = "collected", "Collected"
        RECEIVED = "received", "Received"
        TRANSFERRED = "transferred", "Transferred"
        ALIQUOTED = "aliquoted", "Aliquoted"
        STORED = "stored", "Stored"
        RETRIEVED = "retrieved", "Retrieved"
        SHIPPED = "shipped", "Shipped"
        DISPOSED = "disposed", "Disposed"

    specimen = models.ForeignKey(
        "laboratory.Specimen", on_delete=models.CASCADE, related_name="custody_events"
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    timestamp = models.DateTimeField(default=timezone.now)
    from_custodian = models.CharField(max_length=150, null=True, blank=True)
    to_custodian = models.CharField(max_length=150, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    temperature = models.CharField(max_length=32, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    signature = models.ForeignKey(
        "compliance.ElectronicSignature", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="custody_events",
    )

    class Meta:
        db_table = "coc_events"
        ordering = ["timestamp"]
        indexes = [models.Index(fields=["specimen", "timestamp"])]

    def __str__(self) -> str:
        return f"{self.specimen_id} {self.event_type} @ {self.timestamp:%Y-%m-%d %H:%M}"


class Aliquot(IdentifiedModel):
    """A child specimen derived from a parent, retaining the custody chain."""

    parent = models.ForeignKey(
        "laboratory.Specimen", on_delete=models.CASCADE, related_name="aliquots"
    )
    aliquot_specimen = models.OneToOneField(
        "laboratory.Specimen", on_delete=models.CASCADE, related_name="derived_from"
    )
    volume = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=16, default="mL")
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=150)
    purpose = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "aliquots"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"aliquot of {self.parent_id}"


# ── Unified exception queue ──────────────────────────────────────────────────


class ExceptionSource(models.TextChoices):
    """Where an exception came from.

    The list is deliberately concrete rather than a free-text 'category'. An
    exception queue is only useful if you can ask "how many specimen rejections
    this week", and you cannot ask that of free text.
    """

    SPECIMEN_REJECTION = "specimen_rejection", "Specimen rejected"
    CRITICAL_VALUE = "critical_value", "Critical value unacknowledged"
    DELTA_CHECK = "delta_check", "Delta check flagged"
    TAT_BREACH = "tat_breach", "Turnaround time breached"
    QC_FAILURE = "qc_failure", "Quality control failure"
    INSTRUMENT = "instrument", "Instrument message failed"
    INTERFACE_STALE = "interface_stale", "Instrument interface silent"
    INBOUND_MESSAGE = "inbound_message", "Inbound message could not be processed"
    WEBHOOK = "webhook", "Webhook delivery failing"
    RULE = "rule", "Raised by a decision rule"
    AMENDED_REPORT = "amended_report", "Report amended after release"
    PROFICIENCY = "proficiency", "Proficiency testing deadline"
    SUBJECT_REQUEST = "subject_request", "Data subject request due"
    MANUAL = "manual", "Raised by a person"


class ExceptionItemQuerySet(models.QuerySet):
    def open(self):
        return self.filter(status__in=[
            ExceptionItem.Status.OPEN, ExceptionItem.Status.ACKNOWLEDGED
        ])

    def overdue(self):
        return self.open().filter(due_at__lt=timezone.now())

    def for_user(self, user):
        """Everything this user could act on: theirs, plus anything unassigned."""
        return self.open().filter(
            models.Q(assigned_to=user) | models.Q(assigned_to__isnull=True)
        )


class ExceptionItem(IdentifiedModel):
    """One thing that needs a person's attention, from anywhere in the system.

    Before this existed the same information was spread across eight screens:
    rejected specimens on receiving, unacknowledged criticals on the clinical
    screen, breached turnaround on the TAT report, failed QC on quality, failed
    instrument messages in the interface log, and so on. Each was watched by
    whoever remembered to watch it, which is another way of saying some were
    not watched at all.

    Items are **deduplicated by ``source_key``**: the same underlying problem
    seen twice increments ``occurrences`` rather than creating a second row, so
    a sweep can run every minute without flooding the queue.

    Resolution is recorded, not implied. An item that disappears because the
    underlying condition cleared is still closed explicitly, with a reason, so
    the queue doubles as a record of what the laboratory actually dealt with —
    which is what ISO 15189 §8.7 asks for when it requires nonconformities to
    be managed rather than merely noticed.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    source = models.CharField(max_length=32, choices=ExceptionSource.choices)
    source_key = models.CharField(
        max_length=255, unique=True,
        help_text="Stable identity of the underlying problem, for deduplication.",
    )
    title = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    severity = models.CharField(
        max_length=16, choices=Severity.choices, default=Severity.MEDIUM
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)

    order = models.ForeignKey(
        "laboratory.Order", null=True, blank=True, on_delete=models.CASCADE,
        related_name="exceptions",
    )
    patient = models.ForeignKey(
        "patients.Patient", null=True, blank=True, on_delete=models.CASCADE,
        related_name="exceptions",
    )
    test_code = models.CharField(max_length=64, blank=True)
    entity_type = models.CharField(max_length=64, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)

    raised_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    occurrences = models.PositiveIntegerField(default=1)
    due_at = models.DateTimeField(null=True, blank=True)

    assigned_to = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assigned_exceptions",
    )
    acknowledged_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="acknowledged_exceptions",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="resolved_exceptions",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(blank=True)
    corrective_action = models.ForeignKey(
        "compliance.CorrectiveAction", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="exceptions",
    )

    objects = ExceptionItemQuerySet.as_manager()

    class Meta:
        db_table = "exception_queue"
        # Severity is a readable string, so it does not sort by importance in
        # SQL. The queue view annotates a rank and orders by that; the default
        # here is newest-first, which is right for every other use.
        ordering = ["-raised_at"]
        indexes = [
            models.Index(fields=["status", "-raised_at"]),
            models.Index(fields=["source", "status"]),
            models.Index(fields=["assigned_to", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_source_display()}: {self.title}"

    @property
    def is_open(self) -> bool:
        return self.status in (self.Status.OPEN, self.Status.ACKNOWLEDGED)

    @property
    def is_overdue(self) -> bool:
        return bool(self.is_open and self.due_at and self.due_at < timezone.now())

    @property
    def age_hours(self) -> float:
        return (timezone.now() - self.raised_at).total_seconds() / 3600.0

    @property
    def accession(self) -> str:
        return self.order.accession_number if self.order_id else ""

    # ── Redacted views, for roles barred from patient data ───────────────────

    @property
    def safe_title(self) -> str:
        """The nature of the problem without the specimen it happened to."""
        return self.get_source_display()

    @property
    def safe_detail(self) -> str:
        return "[redacted — contains patient or specimen detail]"


# ── Business continuity ──────────────────────────────────────────────────────


class DowntimeEventQuerySet(models.QuerySet):
    def open(self):
        return self.filter(ended_at__isnull=True)

    def current(self):
        return self.open().order_by("-declared_at").first()


class DowntimeEvent(IdentifiedModel):
    """A period during which the laboratory worked without the system.

    Every accreditation body asks the same question at inspection: *show me
    what you do when the LIS is down*. A laboratory does not stop. It runs on
    paper, and when the system returns, those results have to reach the record
    — identifiably, with the time they were actually produced and the person
    who actually produced them, not the person who typed them in afterwards.

    CLIA §493.1105 and §493.1291 require the report to carry the date and
    identity of the person performing the test; ISO 15189 §8.7 treats an
    unplanned outage as a nonconformity to be managed; CAP asks for a
    documented downtime procedure that has been *tested*. This model is the
    record all three want: what happened, how long, what was produced on
    paper, and when it was reconciled.

    A planned outage is declared before it starts; an unplanned one is declared
    once somebody notices, and ``began_at`` can be backdated to when the
    laboratory actually lost the system rather than when it was logged.
    """

    class Kind(models.TextChoices):
        PLANNED = "planned", "Planned (maintenance, upgrade, migration)"
        UNPLANNED = "unplanned", "Unplanned (outage, failure, network loss)"
        DRILL = "drill", "Drill (testing the downtime procedure)"

    reference = models.CharField(max_length=32, unique=True, help_text="DT-YYYY-NNNN")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.UNPLANNED)

    #: When the laboratory actually lost the system, which is not always when
    #: somebody got round to recording it.
    began_at = models.DateTimeField(default=timezone.now)
    declared_at = models.DateTimeField(default=timezone.now, editable=False)
    declared_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="declared_downtime",
    )
    expected_end = models.DateTimeField(null=True, blank=True)

    reason = models.TextField(help_text="What happened, in the words you would use to an inspector.")
    impact = models.TextField(
        blank=True,
        help_text="Which disciplines and which workflows were affected.",
    )

    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="ended_downtime",
    )
    recovery_notes = models.TextField(blank=True)

    #: Reconciliation. An outage is not closed when the system comes back; it
    #: is closed when everything produced on paper is in the record.
    backloaded_results = models.PositiveIntegerField(default=0, editable=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reconciled_downtime",
    )
    corrective_action = models.ForeignKey(
        "compliance.CorrectiveAction", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="downtime_events",
    )

    objects = DowntimeEventQuerySet.as_manager()

    class Meta:
        db_table = "downtime_events"
        ordering = ["-began_at"]
        indexes = [models.Index(fields=["ended_at", "-began_at"])]

    def __str__(self) -> str:
        return f"{self.reference} — {self.get_kind_display()}"

    @property
    def is_open(self) -> bool:
        return self.ended_at is None

    @property
    def is_reconciled(self) -> bool:
        return self.reconciled_at is not None

    @property
    def duration_hours(self) -> float:
        end = self.ended_at or timezone.now()
        return (end - self.began_at).total_seconds() / 3600.0

    @property
    def needs_reconciliation(self) -> bool:
        """Ended, but nobody has confirmed the paper results are all in."""
        return self.ended_at is not None and self.reconciled_at is None


class DowntimePack(IdentifiedModel):
    """A record that a downtime pack was generated, and what was in it.

    The pack itself is a self-contained HTML file written to disk — it has to
    be readable with no server, no database and no network, because those are
    exactly what is missing when it is needed.

    This row exists so that "was the pack current when the system went down?"
    is answerable. A downtime pack generated three weeks ago is worse than
    none, because people trust it.
    """

    generated_at = models.DateTimeField(default=timezone.now)
    path = models.CharField(max_length=512)
    encrypted = models.BooleanField(default=False)
    order_count = models.PositiveIntegerField(default=0)
    patient_count = models.PositiveIntegerField(default=0)
    bytes_written = models.PositiveIntegerField(default=0)
    generated_by = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = "downtime_packs"
        ordering = ["-generated_at"]

    def __str__(self) -> str:
        return f"downtime pack {self.generated_at:%Y-%m-%d %H:%M}"

    @property
    def age_hours(self) -> float:
        return (timezone.now() - self.generated_at).total_seconds() / 3600.0

    @property
    def is_stale(self) -> bool:
        """Older than a shift. A stale pack is a trap, not a safety net."""
        return self.age_hours > 12
