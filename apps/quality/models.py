"""Quality control, instrument records and specimen rejection criteria."""
from __future__ import annotations

import statistics
from datetime import timedelta

from django.db import models
from django.utils import timezone

from apps.common.models import ActivatableModel, ActiveQuerySet, IdentifiedModel


class RejectionCriterion(IdentifiedModel, ActivatableModel):
    class Category(models.TextChoices):
        QUANTITY = "Quantity", "Quantity"
        QUALITY = "Quality", "Quality"
        LABELING = "Labeling", "Labelling"
        TRANSPORT = "Transport", "Transport"
        GENERAL = "General", "General"

    reason = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.GENERAL)

    class Meta:
        db_table = "rejection_criteria"
        ordering = ["category", "reason"]

    def __str__(self) -> str:
        return self.reason


class QcMaterial(IdentifiedModel, ActivatableModel):
    name = models.CharField(max_length=255)
    lot_number = models.CharField(max_length=64)
    expiration_date = models.DateField()
    manufacturer = models.CharField(max_length=255, null=True, blank=True)
    level = models.CharField(max_length=32, null=True, blank=True, help_text="e.g. Level 1, Normal, High")

    class Meta:
        db_table = "qc_materials"
        ordering = ["name", "lot_number"]

    def __str__(self) -> str:
        return f"{self.name} (lot {self.lot_number})"

    @property
    def is_expired(self) -> bool:
        return self.expiration_date < timezone.localdate()


class QcDefinition(IdentifiedModel):
    """Target mean and SD for one analyte on one control material."""

    material = models.ForeignKey(QcMaterial, on_delete=models.CASCADE, related_name="definitions")
    test = models.ForeignKey(
        "laboratory.TestDefinition", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="qc_definitions",
    )
    test_code = models.CharField(max_length=64)
    test_name = models.CharField(max_length=255)
    mean = models.FloatField()
    sd = models.FloatField()
    unit = models.CharField(max_length=64)

    class Meta:
        db_table = "qc_definitions"
        ordering = ["test_code"]
        constraints = [
            models.UniqueConstraint(fields=["material", "test_code"], name="qc_definition_unique")
        ]

    def __str__(self) -> str:
        return f"{self.test_code} on {self.material_id}"

    def z_score(self, value: float) -> float | None:
        if not self.sd:
            return None
        return (value - self.mean) / self.sd

    def limits(self, sd_multiple: float = 2.0) -> tuple[float, float]:
        return self.mean - sd_multiple * self.sd, self.mean + sd_multiple * self.sd


class QcRunQuerySet(models.QuerySet):
    def recent_for(self, definition, limit: int = 10):
        return self.filter(definition=definition).order_by("-timestamp")[:limit]


class QcRun(IdentifiedModel):
    """One control measurement, evaluated against the Westgard multirules."""

    class Status(models.TextChoices):
        PASS = "Pass", "Pass"
        WARNING = "Warning", "Warning"
        FAIL = "Fail", "Fail"

    definition = models.ForeignKey(QcDefinition, on_delete=models.CASCADE, related_name="runs")
    value = models.FloatField()
    z_score = models.FloatField(null=True, blank=True)
    result_flags = models.JSONField(default=list, blank=True, help_text='Westgard rules violated, e.g. ["1-3s"]')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PASS)
    performed_by = models.CharField(max_length=150)
    timestamp = models.DateTimeField(default=timezone.now)
    comments = models.TextField(null=True, blank=True)
    instrument = models.ForeignKey(
        "quality.Equipment", null=True, blank=True, on_delete=models.SET_NULL, related_name="qc_runs"
    )
    corrective_action = models.ForeignKey(
        "compliance.CorrectiveAction", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="qc_runs",
    )
    accepted = models.BooleanField(
        default=True, help_text="False when the run is rejected and must be repeated"
    )

    objects = QcRunQuerySet.as_manager()

    class Meta:
        db_table = "qc_runs"
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["definition", "-timestamp"]), models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.definition_id} = {self.value} ({self.status})"

    @property
    def requires_corrective_action(self) -> bool:
        return self.status == self.Status.FAIL and self.corrective_action_id is None


class EquipmentQuerySet(ActiveQuerySet):
    def calibration_overdue(self):
        """Active instruments past their calibration date — CLIA §493.1254.

        Mirrors ``Equipment.calibration_overdue`` for a single instance.
        """
        return self.filter(active=True, next_calibration_date__lt=timezone.localdate())

    def service_overdue(self):
        return self.filter(active=True, next_service_date__lt=timezone.localdate())


class Equipment(IdentifiedModel, ActivatableModel):
    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        MAINTENANCE = "Maintenance", "Under maintenance"
        RETIRED = "Retired", "Retired"

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=128)
    serial_number = models.CharField(max_length=128, null=True, blank=True)
    manufacturer = models.CharField(max_length=255, null=True, blank=True)
    department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="equipment"
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    last_service_date = models.DateField(null=True, blank=True)
    next_service_date = models.DateField(null=True, blank=True)
    last_calibration_date = models.DateField(null=True, blank=True)
    next_calibration_date = models.DateField(null=True, blank=True)

    objects = EquipmentQuerySet.as_manager()

    class Meta:
        db_table = "equipment"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def service_overdue(self) -> bool:
        return bool(self.next_service_date and self.next_service_date < timezone.localdate())

    @property
    def calibration_overdue(self) -> bool:
        """CLIA §493.1254 requires calibration at the manufacturer's interval."""
        return bool(self.next_calibration_date and self.next_calibration_date < timezone.localdate())

    @property
    def usable(self) -> bool:
        return self.active and self.status == self.Status.ACTIVE and not self.calibration_overdue


class EquipmentLog(IdentifiedModel):
    class Kind(models.TextChoices):
        MAINTENANCE = "Maintenance", "Maintenance"
        CALIBRATION = "Calibration", "Calibration"
        ERROR = "Error", "Error"
        REPAIR = "Repair", "Repair"
        VERIFICATION = "Verification", "Function verification"

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="logs")
    type = models.CharField(max_length=32, choices=Kind.choices)
    description = models.TextField()
    performed_by = models.CharField(max_length=150)
    timestamp = models.DateTimeField(default=timezone.now)
    outcome = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "equipment_logs"
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.equipment_id} {self.type} @ {self.timestamp:%Y-%m-%d}"


def evaluate_westgard(definition: QcDefinition, value: float, history: list[float]) -> tuple[str, list[str]]:
    """Apply the Westgard multirule set to a new control value.

    ``history`` is the preceding values for the same control, most recent first.
    Returns the run status and the list of rules violated.

    Rules implemented: 1-2s (warning), 1-3s, 2-2s, R-4s, 4-1s and 10x.
    """
    violations: list[str] = []
    if not definition.sd:
        return QcRun.Status.PASS, violations

    series = [value] + list(history)
    z_values = [definition.z_score(v) for v in series]
    z = z_values[0]
    if z is None:
        return QcRun.Status.PASS, violations

    # 1-3s: a single point beyond 3 SD — rejection.
    if abs(z) > 3:
        violations.append("1-3s")
    # 1-2s: a single point beyond 2 SD — warning only.
    elif abs(z) > 2:
        violations.append("1-2s")

    # 2-2s: two consecutive points beyond the same 2 SD limit.
    if len(z_values) >= 2 and all(v is not None for v in z_values[:2]):
        if all(v > 2 for v in z_values[:2]) or all(v < -2 for v in z_values[:2]):
            violations.append("2-2s")

    # R-4s: range between two consecutive points exceeds 4 SD.
    if len(z_values) >= 2 and z_values[1] is not None:
        if abs(z_values[0] - z_values[1]) > 4:
            violations.append("R-4s")

    # 4-1s: four consecutive points beyond the same 1 SD limit.
    if len(z_values) >= 4 and all(v is not None for v in z_values[:4]):
        if all(v > 1 for v in z_values[:4]) or all(v < -1 for v in z_values[:4]):
            violations.append("4-1s")

    # 10x: ten consecutive points on the same side of the mean.
    if len(z_values) >= 10 and all(v is not None for v in z_values[:10]):
        if all(v > 0 for v in z_values[:10]) or all(v < 0 for v in z_values[:10]):
            violations.append("10x")

    rejecting = {"1-3s", "2-2s", "R-4s", "4-1s", "10x"}
    if rejecting & set(violations):
        return QcRun.Status.FAIL, violations
    if violations:
        return QcRun.Status.WARNING, violations
    return QcRun.Status.PASS, violations
