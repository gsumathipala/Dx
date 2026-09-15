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


class Icd10Code(IdentifiedModel):
    """An ICD-10 diagnosis code.

    A laboratory needs diagnosis codes for three separate reasons, and it is
    worth being clear which is which because they pull in different directions:

    * **Clinical context.** "Sodium 128" means something different on a patient
      coded E87.1 (hyponatraemia, already known) than on one coded R55
      (syncope, being worked up). Rules can condition on the code; an
      interpretive comment can say something useful rather than generic.
    * **Medical necessity.** Payers in several jurisdictions will only
      reimburse a test when the indication justifies it. The code travels with
      the order so the claim can be built without a second round trip to the
      requester.
    * **Epidemiology.** Coded indications are what make "how many D-dimers did
      we run for suspected PE last quarter" a query rather than a project.

    Only the code, its description and its chapter are stored. The full ICD-10
    hierarchy, its inclusion and exclusion notes and its national modifications
    belong to whoever licenses it; this is a lookup table, not a terminology
    server.
    """

    code = models.CharField(max_length=16, unique=True)
    description = models.TextField()
    chapter = models.CharField(
        max_length=255, blank=True, help_text="e.g. 'Endocrine, nutritional and metabolic diseases'"
    )
    category = models.CharField(
        max_length=16, blank=True, help_text="The three-character parent, e.g. E87 for E87.1"
    )
    billable = models.BooleanField(
        default=True,
        help_text="False for a category heading that is not itself codeable to a claim.",
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "icd10_codes"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["billable"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.description[:60]}"

    @property
    def is_current(self) -> bool:
        today = timezone.localdate()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_to and today > self.valid_to:
            return False
        return True


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

    # ── Redacted views, for roles barred from patient data ───────────────────
    #
    # A raw ASTM or HL7 message contains the patient's name and identifiers in
    # its PID segment, and the accession number identifies their specimen. An
    # installer diagnosing an interface needs to know that a message arrived,
    # from which analyser, whether it parsed, and what went wrong — none of
    # which requires seeing the payload.

    @property
    def safe_accession(self) -> str:
        return "[redacted]"

    @property
    def safe_payload(self) -> str:
        return f"[redacted — {len(self.raw_payload or '')} characters]"

    @property
    def payload_size(self) -> int:
        return len(self.raw_payload or "")


class HostQuery(IdentifiedModel):
    """An analyser asking the LIS what to run on a specimen it has just loaded.

    This is the missing half of a bidirectional interface. Without it, a
    specimen reaching an analyser carries no work list: either every specimen
    is run for every test on the analyser (wasteful, and it consumes reagent
    that then cannot be used on a request that needed it), or somebody keys the
    request into the analyser by hand, which is the transcription error the
    interface existed to remove.

    With host query, the analyser reads the barcode, asks the LIS what is
    ordered for that specimen, and runs exactly that.

    Flow
    ----
    1. The analyser sends an ASTM query record (``Q``) or an HL7 ``QBP^Q11``.
    2. The instrument server asks the LIS over
       ``POST /api/middleware/query/`` with the specimen identifier.
    3. The LIS answers with the outstanding test codes for that specimen.
    4. The instrument server replies to the analyser in its own dialect and
       records the exchange here.

    Every query is stored because "the analyser says it was never told to run
    that" is a real dispute, and the answer has to exist somewhere other than a
    log file that rotated a week ago.
    """

    class Status(models.TextChoices):
        ANSWERED = "answered", "Answered"
        NOT_FOUND = "not_found", "No matching specimen"
        NO_WORK = "no_work", "Nothing outstanding"
        REFUSED = "refused", "Refused"

    interface = models.ForeignKey(
        InstrumentInterface, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="queries",
    )
    specimen_identifier = models.CharField(
        max_length=64, db_index=True,
        help_text="What the analyser read from the tube — accession or container id.",
    )
    order = models.ForeignKey(
        "laboratory.Order", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="host_queries",
    )
    requested_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ANSWERED)
    tests = models.JSONField(
        default=list, blank=True, help_text="Test codes returned to the analyser."
    )
    detail = models.TextField(blank=True)
    response_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "host_queries"
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["interface", "-requested_at"]),
            models.Index(fields=["status", "-requested_at"]),
        ]

    def __str__(self) -> str:
        return f"query {self.specimen_identifier} → {self.status}"

    @property
    def test_count(self) -> int:
        return len(self.tests or [])

    # ── Redacted views, for roles barred from patient data ───────────────────
    #
    # A specimen identifier resolves to a patient, and a list of ordered tests
    # is a clinical statement about them. Someone verifying that host query is
    # working needs the interface, the time, the outcome and the latency.

    @property
    def safe_identifier(self) -> str:
        return "[redacted]"

    @property
    def safe_tests(self) -> str:
        return f"{self.test_count} test(s)"
