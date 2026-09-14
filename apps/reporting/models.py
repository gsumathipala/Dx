"""Controlled documents, report distribution and requester registry."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import ActivatableModel, IdentifiedModel


class ControlledDocument(IdentifiedModel):
    """A version-controlled SOP, policy or manual (ISO 15189 §8.3).

    Document control requires an approval step, a defined review cycle, and
    evidence that staff have read the current version — the last of which is
    held in ``compliance.DocumentAcknowledgement``.
    """

    class Category(models.TextChoices):
        SOP = "SOP", "Standard operating procedure"
        POLICY = "Policy", "Policy"
        MANUAL = "Manual", "Manual"
        FORM = "Form", "Form"
        SAFETY = "Safety", "Safety data sheet"
        VALIDATION = "Validation", "Validation report"

    class Status(models.TextChoices):
        DRAFT = "Draft", "Draft"
        IN_REVIEW = "In Review", "In review"
        ACTIVE = "Active", "Active"
        SUPERSEDED = "Superseded", "Superseded"
        ARCHIVED = "Archived", "Archived"
        OBSOLETE = "Obsolete", "Obsolete"

    title = models.CharField(max_length=255)
    document_number = models.CharField(max_length=64, null=True, blank=True)
    category = models.CharField(max_length=32, choices=Category.choices)
    version = models.CharField(max_length=32)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    file = models.FileField(upload_to="documents/%Y/%m/", null=True, blank=True)
    uploaded_by = models.CharField(max_length=150, null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)
    effective_date = models.DateField(null=True, blank=True)
    review_due = models.DateField(null=True, blank=True, help_text="Scheduled periodic review")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="approved_documents",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="superseded_by"
    )
    requires_acknowledgement = models.BooleanField(default=True)
    department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="documents",
    )

    class Meta:
        db_table = "documents"
        ordering = ["category", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["document_number", "version"],
                name="document_number_version_unique",
                condition=models.Q(document_number__isnull=False),
            )
        ]

    def __str__(self) -> str:
        return f"{self.title} v{self.version}"

    @property
    def is_current(self) -> bool:
        return self.status == self.Status.ACTIVE

    @property
    def review_overdue(self) -> bool:
        return bool(
            self.status == self.Status.ACTIVE
            and self.review_due
            and self.review_due < timezone.localdate()
        )

    def outstanding_acknowledgements(self):
        """Users who have not yet acknowledged the current version."""
        from django.contrib.auth import get_user_model

        acknowledged = self.acknowledgements.filter(document_version=self.version).values_list(
            "user_id", flat=True
        )
        return get_user_model().objects.filter(is_active=True).exclude(pk__in=acknowledged)


class Requester(IdentifiedModel, ActivatableModel):
    """A referring clinician, ward, clinic or external organisation."""

    class Kind(models.TextChoices):
        GP = "GP", "General practitioner"
        WARD = "Ward", "Ward"
        CLINIC = "Clinic", "Clinic"
        HOSPITAL = "Hospital", "Hospital"
        EXTERNAL = "External", "External laboratory"

    class Delivery(models.TextChoices):
        PORTAL = "portal", "Portal"
        EMAIL = "email", "Email"
        PRINT = "print", "Print"
        FAX = "fax", "Fax"
        HL7 = "hl7", "HL7 interface"

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=32, choices=Kind.choices)
    contact_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=64, null=True, blank=True)
    fax = models.CharField(max_length=64, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    delivery_preference = models.CharField(
        max_length=16, choices=Delivery.choices, default=Delivery.PORTAL
    )
    created_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "requesters"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DistributionRule(IdentifiedModel, ActivatableModel):
    """How a given requester's reports are delivered."""

    requester = models.ForeignKey(
        Requester, null=True, blank=True, on_delete=models.CASCADE, related_name="distribution_rules"
    )
    test = models.ForeignKey(
        "laboratory.TestDefinition", null=True, blank=True, on_delete=models.CASCADE,
        related_name="distribution_rules",
    )
    method = models.CharField(max_length=16, choices=Requester.Delivery.choices)
    destination = models.CharField(max_length=255, null=True, blank=True)
    auto_release = models.BooleanField(
        default=False, help_text="Send as soon as the report is clinically verified"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "distribution_rules"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.requester_id or 'any'} via {self.method}"


class DistributionLog(IdentifiedModel):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        SENT = "Sent", "Sent"
        FAILED = "Failed", "Failed"

    order = models.ForeignKey(
        "laboratory.Order", on_delete=models.CASCADE, related_name="distributions"
    )
    rule = models.ForeignKey(
        DistributionRule, null=True, blank=True, on_delete=models.SET_NULL, related_name="logs"
    )
    method = models.CharField(max_length=16)
    destination = models.CharField(max_length=255, null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "distribution_logs"
        ordering = ["-sent_at"]

    def __str__(self) -> str:
        return f"{self.order_id} via {self.method} ({self.status})"


class EmailQueueEntry(IdentifiedModel):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        SENT = "Sent", "Sent"
        FAILED = "Failed", "Failed"

    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField(null=True, blank=True)
    attachment_path = models.CharField(max_length=512, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    order = models.ForeignKey(
        "laboratory.Order", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="emails",
    )

    class Meta:
        db_table = "email_queue"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"{self.recipient}: {self.subject}"
