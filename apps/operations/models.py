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
        django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages"
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
