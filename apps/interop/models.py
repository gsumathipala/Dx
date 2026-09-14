"""Interoperability: LOINC catalogue and instrument interface records."""
from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.common.models import IdentifiedModel


class LoincCode(IdentifiedModel):
    """LOINC catalogue entry used to code tests for external exchange."""

    class Scale(models.TextChoices):
        QUANTITATIVE = "Qn", "Quantitative"
        ORDINAL = "Ord", "Ordinal"
        NOMINAL = "Nom", "Nominal"
        NARRATIVE = "Nar", "Narrative"

    loinc_code = models.CharField(max_length=32, unique=True)
    long_name = models.TextField()
    short_name = models.CharField(max_length=255, null=True, blank=True)
    component = models.CharField(max_length=255, null=True, blank=True)
    property = models.CharField(max_length=64, null=True, blank=True)
    time_aspect = models.CharField(max_length=64, null=True, blank=True)
    system = models.CharField(max_length=128, null=True, blank=True)
    scale = models.CharField(max_length=8, choices=Scale.choices, null=True, blank=True)
    method = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=32, default="Active")

    class Meta:
        db_table = "loinc_codes"
        ordering = ["loinc_code"]
        indexes = [models.Index(fields=["component"])]

    def __str__(self) -> str:
        return f"{self.loinc_code} — {self.short_name or self.long_name[:60]}"


class InstrumentInterface(IdentifiedModel):
    """A configured analyser connection.

    The Python instrument server connects inbound and posts parsed messages to
    the ingest endpoint using this record's token.
    """

    class Protocol(models.TextChoices):
        ASTM = "astm", "ASTM E1381/E1394"
        HL7 = "hl7", "HL7 v2 (MLLP)"
        POCT1A = "poct1a", "POCT1-A"
        CSV = "csv", "Delimited file"

    class Direction(models.TextChoices):
        UNIDIRECTIONAL = "uni", "Unidirectional (results only)"
        BIDIRECTIONAL = "bi", "Bidirectional (orders and results)"

    name = models.CharField(max_length=255)
    equipment = models.ForeignKey(
        "quality.Equipment", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="interfaces",
    )
    protocol = models.CharField(max_length=16, choices=Protocol.choices, default=Protocol.ASTM)
    direction = models.CharField(
        max_length=8, choices=Direction.choices, default=Direction.UNIDIRECTIONAL
    )
    host = models.CharField(max_length=255, null=True, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    test_code_map = models.JSONField(
        default=dict, blank=True, help_text="Instrument code → Dx test code"
    )

    class Meta:
        db_table = "instrument_interfaces"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_stale(self) -> bool:
        """No traffic for over an hour on an enabled interface."""
        if not self.enabled or self.last_message_at is None:
            return self.enabled
        return (timezone.now() - self.last_message_at).total_seconds() > 3600


class InstrumentMessage(IdentifiedModel):
    """Raw inbound instrument traffic, retained for troubleshooting and audit."""

    class Status(models.TextChoices):
        RECEIVED = "Received", "Received"
        PARSED = "Parsed", "Parsed"
        APPLIED = "Applied", "Applied to results"
        FAILED = "Failed", "Failed"
        IGNORED = "Ignored", "Ignored"

    interface = models.ForeignKey(
        InstrumentInterface, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="messages",
    )
    received_at = models.DateTimeField(default=timezone.now)
    raw_payload = models.TextField()
    parsed_payload = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED)
    accession_number = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    error = models.TextField(null=True, blank=True)
    results_applied = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "instrument_messages"
        ordering = ["-received_at"]
        indexes = [models.Index(fields=["status", "-received_at"])]

    def __str__(self) -> str:
        return f"{self.interface_id or 'unknown'} @ {self.received_at:%Y-%m-%d %H:%M} ({self.status})"
