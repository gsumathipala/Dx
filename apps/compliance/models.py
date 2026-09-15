"""Regulatory records and controls.

Each model here exists to satisfy a specific obligation; the citation on the
class says which one. The controls are enforced by
``apps.compliance.services`` rather than merely recorded, because an
unenforced control is an inspection finding.

Frameworks covered
------------------
* CLIA '88 (42 CFR 493) — competency, QC, proficiency testing, method
  validation, record retention.
* 21 CFR Part 11 — electronic records and signatures.
* CAP / ISO 15189:2022 — document control, CAPA, critical value read-back,
  amended reports, risk management.
* HIPAA Privacy & Security Rules — PHI access logging, disclosure accounting.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import ActivatableModel, IdentifiedModel


# ── 21 CFR Part 11: electronic signatures ────────────────────────────────────


class ElectronicSignature(IdentifiedModel):
    """A Part 11 compliant signature (§11.50, §11.70, §11.200).

    §11.50 requires the signed record to display the signer's printed name, the
    date and time of signing, and the *meaning* of the signature. §11.70
    requires the signature to be bound to its record so it cannot be excised
    and reapplied elsewhere — here the binding is the SHA-256 ``record_hash``
    of the content at signing time plus the linked audit event.
    """

    class Meaning(models.TextChoices):
        AUTHORSHIP = "authorship", "Authored by"
        REVIEW = "review", "Reviewed by"
        TECHNICAL_APPROVAL = "technical_approval", "Technically approved by"
        CLINICAL_APPROVAL = "clinical_approval", "Clinically approved by"
        RELEASE = "release", "Released by"
        ACKNOWLEDGEMENT = "acknowledgement", "Acknowledged by"
        CORRECTION = "correction", "Corrected by"
        TRAINING = "training", "Training completed by"
        AUTO_VERIFICATION = "auto_verification", "Autoverified by rule"

    #: Null when the signer is not a person. A result released by a decision
    #: rule is signed by the rule, at the version that fired — recording the
    #: user who happened to be in session would be false attribution, which is
    #: a graver Part 11 finding than having no human signature at all.
    signer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="electronic_signatures",
    )
    automated_rule = models.ForeignKey(
        "rules.Rule", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="signatures", help_text="Set when the signer is a rule, not a person.",
    )
    signer_printed_name = models.CharField(
        max_length=255, help_text="Captured at signing time — §11.50(a)(1)"
    )
    signer_role = models.CharField(max_length=32)
    signed_at = models.DateTimeField(default=timezone.now)
    meaning = models.CharField(max_length=32, choices=Meaning.choices)

    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    record_hash = models.CharField(
        max_length=64, help_text="SHA-256 of the signed content — binds signature to record (§11.70)"
    )
    audit_sequence = models.BigIntegerField(
        null=True, blank=True, help_text="Position of the corresponding audit event"
    )

    reauthenticated = models.BooleanField(
        default=False, help_text="Signer re-entered their password at signing (§11.200(a)(1))"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "electronic_signatures"
        ordering = ["-signed_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["signer", "-signed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_meaning_display()} {self.signer_printed_name} @ {self.signed_at:%Y-%m-%d %H:%M}"

    @property
    def is_automated(self) -> bool:
        return self.signer_id is None

    @property
    def manifest(self) -> str:
        """The human-readable signature block printed on reports (§11.50).

        An automated signature says so in plain words. A clinician reading a
        report is entitled to know whether a person looked at the result.
        """
        if self.is_automated:
            return (
                f"{self.get_meaning_display()}: {self.signer_printed_name} "
                f"— no human review — {self.signed_at:%Y-%m-%d %H:%M:%S %Z}"
            )
        return (
            f"{self.get_meaning_display()}: {self.signer_printed_name} "
            f"({self.signer_role}) — {self.signed_at:%Y-%m-%d %H:%M:%S %Z}"
        )

    def delete(self, *args, **kwargs):  # pragma: no cover - defensive
        raise RuntimeError("Electronic signatures are permanent records and cannot be deleted.")


class PasswordHistory(models.Model):
    """Prevents password reuse (§11.300(b) — periodic ageing/recall)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_history"
    )
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_history"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.created_at:%Y-%m-%d}"


class AccountSecurityState(models.Model):
    """Lockout and password-ageing state (§11.300(d))."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_state"
    )
    failed_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_failed_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(default=timezone.now)
    must_change_password = models.BooleanField(default=False)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "account_security_state"

    def __str__(self) -> str:
        return f"security state for {self.user_id}"

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    @property
    def password_expires_at(self):
        days = getattr(settings, "PASSWORD_EXPIRY_DAYS", 90)
        if not days:
            return None
        return self.password_changed_at + timedelta(days=days)

    @property
    def password_expired(self) -> bool:
        expiry = self.password_expires_at
        return bool(expiry and expiry <= timezone.now())


# ── CLIA §493.801: proficiency testing / external quality assessment ─────────


class ProficiencySurveyQuerySet(models.QuerySet):
    def overdue(self):
        """Unsubmitted surveys past their due date.

        Mirrors ``ProficiencySurvey.is_overdue`` for a single instance.
        """
        return self.filter(submitted_date__isnull=True, due_date__lt=timezone.localdate())


class ProficiencySurvey(IdentifiedModel):
    """A PT/EQA survey shipment from an approved provider."""

    provider = models.CharField(max_length=255, help_text="e.g. CAP, RCPA, UK NEQAS")
    survey_code = models.CharField(max_length=64)
    year = models.PositiveIntegerField()
    event = models.CharField(max_length=32, help_text="Shipment/event within the year")
    discipline = models.CharField(max_length=128)
    received_date = models.DateField(null=True, blank=True)
    due_date = models.DateField()
    submitted_date = models.DateField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="pt_submissions",
    )
    attestation_signed = models.BooleanField(
        default=False,
        help_text="Attests no inter-laboratory communication occurred — CLIA §493.801(b)(4)",
    )
    notes = models.TextField(null=True, blank=True)

    objects = ProficiencySurveyQuerySet.as_manager()

    class Meta:
        db_table = "proficiency_surveys"
        ordering = ["-year", "-event"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "survey_code", "year", "event"], name="pt_survey_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider} {self.survey_code} {self.year}-{self.event}"

    @property
    def is_overdue(self) -> bool:
        return self.submitted_date is None and self.due_date < timezone.localdate()


class ProficiencyResult(IdentifiedModel):
    """A single analyte result within a PT survey, with its grade."""

    class Grade(models.TextChoices):
        ACCEPTABLE = "Acceptable", "Acceptable"
        UNACCEPTABLE = "Unacceptable", "Unacceptable"
        NOT_GRADED = "Not Graded", "Not graded"

    survey = models.ForeignKey(ProficiencySurvey, on_delete=models.CASCADE, related_name="results")
    test = models.ForeignKey(
        "laboratory.TestDefinition", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="pt_results",
    )
    analyte = models.CharField(max_length=128)
    sample_id = models.CharField(max_length=64)
    reported_value = models.CharField(max_length=64)
    target_value = models.CharField(max_length=64, null=True, blank=True)
    acceptable_range = models.CharField(max_length=128, null=True, blank=True)
    z_score = models.FloatField(null=True, blank=True)
    grade = models.CharField(max_length=32, choices=Grade.choices, default=Grade.NOT_GRADED)
    corrective_action = models.ForeignKey(
        "compliance.CorrectiveAction", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="pt_results",
    )

    class Meta:
        db_table = "proficiency_results"
        ordering = ["analyte", "sample_id"]

    def __str__(self) -> str:
        return f"{self.analyte} {self.sample_id}: {self.grade}"

    @property
    def requires_corrective_action(self) -> bool:
        """Unacceptable PT performance mandates documented corrective action."""
        return self.grade == self.Grade.UNACCEPTABLE and self.corrective_action_id is None


# ── CLIA §493.1253: method validation / verification ─────────────────────────


class MethodValidation(IdentifiedModel):
    """Establishment or verification of a test's performance specifications.

    CLIA §493.1253(b)(1) requires verification of accuracy, precision,
    reportable range and reference intervals before reporting patient results
    with any non-waived test.
    """

    class Kind(models.TextChoices):
        VERIFICATION = "verification", "Verification (FDA-cleared method)"
        ESTABLISHMENT = "establishment", "Establishment (LDT / modified method)"
        REVALIDATION = "revalidation", "Revalidation"

    class Status(models.TextChoices):
        IN_PROGRESS = "In Progress", "In progress"
        APPROVED = "Approved", "Approved"
        REJECTED = "Rejected", "Rejected"
        SUPERSEDED = "Superseded", "Superseded"

    test = models.ForeignKey(
        "laboratory.TestDefinition", on_delete=models.CASCADE, related_name="validations"
    )
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.VERIFICATION)
    instrument = models.ForeignKey(
        "quality.Equipment", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="validations",
    )
    performed_by = models.CharField(max_length=150)
    started_on = models.DateField()
    completed_on = models.DateField(null=True, blank=True)

    accuracy_verified = models.BooleanField(default=False)
    precision_verified = models.BooleanField(default=False)
    reportable_range_verified = models.BooleanField(default=False)
    reference_interval_verified = models.BooleanField(default=False)
    analytical_sensitivity = models.CharField(max_length=128, null=True, blank=True)
    analytical_specificity = models.CharField(max_length=128, null=True, blank=True)

    summary = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.IN_PROGRESS)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="approved_validations",
    )
    approved_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "method_validations"
        ordering = ["-started_on"]

    def __str__(self) -> str:
        return f"{self.test_id} {self.kind} ({self.status})"

    @property
    def all_elements_verified(self) -> bool:
        return all([
            self.accuracy_verified,
            self.precision_verified,
            self.reportable_range_verified,
            self.reference_interval_verified,
        ])


# ── CAP / ISO 15189 §8.7: nonconformance and corrective action ───────────────


class CorrectiveActionQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status=CorrectiveAction.Status.CLOSED)

    def overdue(self):
        """Open nonconformances past their due date.

        Mirrors ``CorrectiveAction.is_overdue`` for a single instance.
        """
        return self.open().filter(due_date__lt=timezone.localdate())


class CorrectiveAction(IdentifiedModel):
    """CAPA record for a nonconformity, incident or complaint."""

    class Category(models.TextChoices):
        QC_FAILURE = "qc_failure", "QC failure"
        PT_FAILURE = "pt_failure", "Proficiency testing failure"
        SPECIMEN = "specimen", "Specimen / pre-analytical"
        INSTRUMENT = "instrument", "Instrument"
        RESULT_ERROR = "result_error", "Result error"
        TAT = "tat", "Turnaround time"
        COMPLAINT = "complaint", "Complaint"
        SAFETY = "safety", "Safety"
        PRIVACY = "privacy", "Privacy / confidentiality"
        OTHER = "other", "Other"

    class Severity(models.TextChoices):
        LOW = "Low", "Low"
        MEDIUM = "Medium", "Medium"
        HIGH = "High", "High"
        CRITICAL = "Critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "Open", "Open"
        INVESTIGATING = "Investigating", "Investigating"
        ACTION_PLANNED = "Action Planned", "Action planned"
        IMPLEMENTED = "Implemented", "Implemented"
        VERIFYING = "Verifying", "Verifying effectiveness"
        CLOSED = "Closed", "Closed"

    reference = models.CharField(max_length=32, unique=True, help_text="CAPA-YYYY-NNNN")
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=Category.choices)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.OPEN)

    description = models.TextField(help_text="What happened")
    immediate_action = models.TextField(null=True, blank=True, help_text="Containment / correction")
    root_cause = models.TextField(null=True, blank=True)
    corrective_action = models.TextField(null=True, blank=True, help_text="To prevent recurrence")
    preventive_action = models.TextField(null=True, blank=True)
    effectiveness_check = models.TextField(null=True, blank=True)

    patient_impact = models.BooleanField(default=False)
    reported_results_affected = models.PositiveIntegerField(default=0)

    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="capas_raised"
    )
    raised_at = models.DateTimeField(default=timezone.now)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="capas_assigned",
    )
    due_date = models.DateField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="capas_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    linked_entity_type = models.CharField(max_length=64, null=True, blank=True)
    linked_entity_id = models.CharField(max_length=64, null=True, blank=True)

    objects = CorrectiveActionQuerySet.as_manager()

    class Meta:
        db_table = "corrective_actions"
        ordering = ["-raised_at"]
        indexes = [models.Index(fields=["status", "-raised_at"])]

    def __str__(self) -> str:
        return f"{self.reference} — {self.title}"

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.due_date
            and self.status != self.Status.CLOSED
            and self.due_date < timezone.localdate()
        )


# ── ISO 15189 §8.3 / CAP: document control and training ──────────────────────


class DocumentAcknowledgement(IdentifiedModel):
    """Evidence that a member of staff has read a controlled document."""

    document = models.ForeignKey(
        "reporting.ControlledDocument", on_delete=models.CASCADE, related_name="acknowledgements"
    )
    document_version = models.CharField(max_length=32)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="document_acknowledgements"
    )
    acknowledged_at = models.DateTimeField(default=timezone.now)
    signature = models.ForeignKey(
        ElectronicSignature, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="document_acknowledgements",
    )

    class Meta:
        db_table = "document_acknowledgements"
        ordering = ["-acknowledged_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "document_version", "user"], name="document_ack_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} acknowledged {self.document_id} v{self.document_version}"


class TrainingRecord(IdentifiedModel):
    """Training delivered and assessed — CLIA §493.1451(b)(8)."""

    class Status(models.TextChoices):
        PLANNED = "Planned", "Planned"
        COMPLETED = "Completed", "Completed"
        FAILED = "Failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="training_records"
    )
    topic = models.CharField(max_length=255)
    document = models.ForeignKey(
        "reporting.ControlledDocument", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="training_records",
    )
    trainer = models.CharField(max_length=150)
    completed_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PLANNED)
    assessment_method = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "training_records"
        ordering = ["-completed_on"]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.topic}"


# ── HIPAA §164.312(b) / §164.528: PHI access and disclosure accounting ───────


class PHIAccessLog(models.Model):
    """Every read of identifiable patient information.

    HIPAA requires the ability to show who looked at a record. This is separate
    from the change audit trail because reads vastly outnumber writes and are
    pruned on a different retention schedule.
    """

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="phi_accesses",
    )
    username = models.CharField(max_length=150, db_index=True)
    patient = models.ForeignKey(
        "patients.Patient", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="access_log",
    )
    patient_mrn = models.CharField(max_length=64, db_index=True, blank=True, default="")
    path = models.CharField(max_length=512)
    method = models.CharField(max_length=8)
    purpose = models.CharField(
        max_length=64, default="treatment",
        help_text="treatment | payment | operations | patient_request | legal",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    break_the_glass = models.BooleanField(
        default=False, help_text="Emergency override of normal access restrictions"
    )
    justification = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "phi_access_log"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["patient", "-timestamp"]),
            models.Index(fields=["username", "-timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.username} viewed {self.patient_mrn or self.patient_id} at {self.timestamp:%Y-%m-%d %H:%M}"


class DisclosureAccounting(IdentifiedModel):
    """Disclosures of PHI to third parties — HIPAA §164.528.

    A patient may request an accounting of disclosures covering the previous
    six years; every release outside treatment/payment/operations is logged.
    """

    class Purpose(models.TextChoices):
        TREATMENT = "treatment", "Treatment"
        PAYMENT = "payment", "Payment"
        OPERATIONS = "operations", "Health care operations"
        PUBLIC_HEALTH = "public_health", "Public health reporting"
        LEGAL = "legal", "Legal / court order"
        PATIENT_REQUEST = "patient_request", "Patient request"
        RESEARCH = "research", "Research"
        OTHER = "other", "Other"

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="disclosures"
    )
    order = models.ForeignKey(
        "laboratory.Order", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="disclosures",
    )
    disclosed_at = models.DateTimeField(default=timezone.now)
    disclosed_by = models.CharField(max_length=150)
    recipient_name = models.CharField(max_length=255)
    recipient_address = models.TextField(null=True, blank=True)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    description = models.TextField(help_text="What information was disclosed")
    method = models.CharField(max_length=32, default="portal")
    authorised_by_patient = models.BooleanField(default=False)

    class Meta:
        db_table = "disclosure_accounting"
        ordering = ["-disclosed_at"]
        indexes = [models.Index(fields=["patient", "-disclosed_at"])]

    def __str__(self) -> str:
        return f"{self.patient_id} → {self.recipient_name} ({self.purpose})"


class PatientConsent(IdentifiedModel):
    """Consent and privacy preferences held against a patient."""

    class Kind(models.TextChoices):
        TREATMENT = "treatment", "Treatment"
        RESEARCH = "research", "Research use"
        DATA_SHARING = "data_sharing", "Data sharing"
        MARKETING = "marketing", "Marketing"
        GENETIC = "genetic", "Genetic testing"

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="consents"
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    granted = models.BooleanField(default=True)
    granted_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.CharField(max_length=150)
    document_reference = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "patient_consents"
        ordering = ["-granted_at"]

    def __str__(self) -> str:
        state = "granted" if self.is_current else "withdrawn"
        return f"{self.patient_id} {self.kind} ({state})"

    @property
    def is_current(self) -> bool:
        return self.granted and self.withdrawn_at is None


# ── CLIA §493.1105: record retention schedule ────────────────────────────────


class RetentionSchedule(IdentifiedModel, ActivatableModel):
    """Minimum retention period per class of record.

    Defaults follow CLIA §493.1105: test requisitions and reports two years,
    immunohaematology five years, pathology reports ten years.
    """

    class RecordClass(models.TextChoices):
        REQUISITION = "requisition", "Test requisition"
        TEST_RECORD = "test_record", "Test record / result"
        QC_RECORD = "qc_record", "Quality control record"
        PT_RECORD = "pt_record", "Proficiency testing record"
        INSTRUMENT = "instrument", "Instrument maintenance record"
        PERSONNEL = "personnel", "Personnel / competency record"
        BLOOD_BANK = "blood_bank", "Immunohaematology record"
        PATHOLOGY = "pathology", "Pathology report"
        CYTOLOGY_SLIDE = "cytology_slide", "Cytology slide"
        HISTOLOGY_BLOCK = "histology_block", "Histology block"
        AUDIT = "audit", "Audit trail"

    record_class = models.CharField(max_length=32, choices=RecordClass.choices, unique=True)
    retention_years = models.PositiveIntegerField()
    citation = models.CharField(max_length=255, help_text="Regulatory basis for the period")
    destruction_method = models.CharField(max_length=128, default="Secure electronic deletion")
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "retention_schedules"
        ordering = ["record_class"]

    def __str__(self) -> str:
        return f"{self.get_record_class_display()} — {self.retention_years}y"


# ── CAP: amended and corrected reports ───────────────────────────────────────


class AmendedReport(IdentifiedModel):
    """A corrected report issued after a result was already released.

    CAP requires the original result to be retained and visible, the report to
    be clearly marked as amended, and the requesting clinician to be notified.
    """

    class Reason(models.TextChoices):
        TRANSCRIPTION = "transcription", "Transcription error"
        ANALYTICAL = "analytical", "Analytical error"
        SPECIMEN_MIXUP = "specimen_mixup", "Specimen identification error"
        INTERPRETATION = "interpretation", "Interpretation change"
        ADDENDUM = "addendum", "Addendum / additional information"
        OTHER = "other", "Other"

    order = models.ForeignKey(
        "laboratory.Order", on_delete=models.CASCADE, related_name="amendments"
    )
    result = models.ForeignKey(
        "laboratory.Result", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="amendments",
    )
    version = models.PositiveIntegerField(default=2, help_text="Report version; 1 is the original")
    reason = models.CharField(max_length=32, choices=Reason.choices)
    original_value = models.TextField(null=True, blank=True)
    corrected_value = models.TextField(null=True, blank=True)
    narrative = models.TextField(help_text="Explanation printed on the amended report")

    amended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="amendments"
    )
    amended_at = models.DateTimeField(default=timezone.now)
    signature = models.ForeignKey(
        ElectronicSignature, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="amendments",
    )

    clinician_notified = models.BooleanField(default=False)
    notified_at = models.DateTimeField(null=True, blank=True)
    notified_by = models.CharField(max_length=150, null=True, blank=True)
    notification_method = models.CharField(max_length=32, null=True, blank=True)
    corrective_action = models.ForeignKey(
        CorrectiveAction, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="amendments",
    )

    class Meta:
        db_table = "amended_reports"
        ordering = ["-amended_at"]
        constraints = [
            models.UniqueConstraint(fields=["order", "version"], name="amended_report_version_unique")
        ]

    def __str__(self) -> str:
        return f"{self.order_id} amendment v{self.version}"


# ── ISO 15189 §8.5: risk management, and Part 11 §11.10(a): validation ───────


class RiskAssessmentQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status=RiskAssessment.Status.CLOSED)

    def with_score(self):
        """Annotate the effective score: residual where present, else inherent."""
        from django.db.models import F, IntegerField
        from django.db.models.functions import Coalesce

        return self.annotate(
            effective_score=Coalesce(
                F("residual_likelihood") * F("residual_severity"),
                F("likelihood") * F("severity"),
                output_field=IntegerField(),
            )
        )

    def high_rated(self):
        """Risks scoring 15 or above. Mirrors ``RiskAssessment.rating``."""
        return self.open().with_score().filter(effective_score__gte=15)


class RiskAssessment(IdentifiedModel):
    """Documented assessment of a risk to examination quality or patient safety."""

    class Status(models.TextChoices):
        IDENTIFIED = "Identified", "Identified"
        MITIGATING = "Mitigating", "Mitigating"
        ACCEPTED = "Accepted", "Accepted (residual)"
        CLOSED = "Closed", "Closed"

    reference = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=255)
    process_area = models.CharField(max_length=128)
    description = models.TextField()
    likelihood = models.PositiveSmallIntegerField(help_text="1 (rare) – 5 (almost certain)")
    severity = models.PositiveSmallIntegerField(help_text="1 (negligible) – 5 (catastrophic)")
    existing_controls = models.TextField(null=True, blank=True)
    mitigation = models.TextField(null=True, blank=True)
    residual_likelihood = models.PositiveSmallIntegerField(null=True, blank=True)
    residual_severity = models.PositiveSmallIntegerField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="risks",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.IDENTIFIED)
    reviewed_on = models.DateField(null=True, blank=True)
    next_review = models.DateField(null=True, blank=True)

    objects = RiskAssessmentQuerySet.as_manager()

    class Meta:
        db_table = "risk_assessments"
        ordering = ["-likelihood", "-severity"]

    def __str__(self) -> str:
        return f"{self.reference} — {self.title}"

    @property
    def risk_score(self) -> int:
        return self.likelihood * self.severity

    @property
    def residual_score(self) -> int | None:
        if self.residual_likelihood and self.residual_severity:
            return self.residual_likelihood * self.residual_severity
        return None

    @property
    def rating(self) -> str:
        score = self.residual_score or self.risk_score
        if score >= 15:
            return "High"
        if score >= 8:
            return "Medium"
        return "Low"


class ChangeControl(IdentifiedModel):
    """System change record — 21 CFR Part 11 §11.10(a) / ISO 15189 §8.2.

    Configuration or software changes affecting result production must be
    assessed, approved and validated before release.
    """

    class Status(models.TextChoices):
        REQUESTED = "Requested", "Requested"
        ASSESSED = "Assessed", "Impact assessed"
        APPROVED = "Approved", "Approved"
        IMPLEMENTED = "Implemented", "Implemented"
        VERIFIED = "Verified", "Verified in production"
        REJECTED = "Rejected", "Rejected"

    reference = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    change_type = models.CharField(max_length=64, help_text="software | configuration | method | instrument")
    impact_assessment = models.TextField(null=True, blank=True)
    validation_evidence = models.TextField(null=True, blank=True)
    rollback_plan = models.TextField(null=True, blank=True)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="change_requests"
    )
    requested_at = models.DateTimeField(default=timezone.now)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="change_approvals",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    implemented_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.REQUESTED)

    class Meta:
        db_table = "change_controls"
        ordering = ["-requested_at"]

    def __str__(self) -> str:
        return f"{self.reference} — {self.title}"


# ── GDPR Chapter III: rights of the data subject ─────────────────────────────


class DataSubjectRequestQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status__in=[
            DataSubjectRequest.Status.COMPLETED,
            DataSubjectRequest.Status.REFUSED,
            DataSubjectRequest.Status.WITHDRAWN,
        ])

    def overdue(self):
        return self.open().filter(due_at__lt=timezone.now())


class DataSubjectRequest(IdentifiedModel):
    """A patient exercising a right over their own data.

    GDPR gives a data subject seven rights; a clinical laboratory can satisfy
    some of them fully, some partially, and must refuse others outright. The
    interesting engineering is in the refusals, because a system that simply
    deletes on request would destroy records the laboratory is legally required
    to keep — and would do so irreversibly.

    Right by right
    --------------
    **Access (Art. 15)** — satisfied in full. The export includes demographics,
    every order, every result, reports issued, and the accounting of
    disclosures. Produced as a signed, encrypted archive.

    **Rectification (Art. 16)** — satisfied, but *not* by overwriting. A
    clinical record is corrected by amendment: the original value stays
    visible, the correction is signed, and anyone who received the original is
    notified. That is CAP's requirement and it happens to be what Art. 19
    asks for too.

    **Erasure (Art. 17)** — ordinarily refused, and the refusal is the
    lawful answer. Art. 17(3)(b) disapplies erasure where processing is
    necessary for compliance with a legal obligation, and 17(3)(c) where it is
    necessary for public health purposes or the provision of health care. CLIA
    §493.1105 requires test records for two years, pathology reports for ten,
    and histopathology slides for ten; several jurisdictions require longer.
    A request is therefore assessed against the retention schedule: anything
    past its retention period *can* be erased and is; anything inside it is
    refused with the specific basis stated, which is what Art. 12(4) requires.

    **Restriction (Art. 18)** — satisfied by flagging the record so it is not
    used for anything beyond storage and the establishment of legal claims.

    **Portability (Art. 20)** — satisfied as a FHIR R4 Bundle, which is a
    "structured, commonly used and machine-readable format" in the sense
    Art. 20(1) means, and is actually loadable by another system, which a CSV
    of our column names would not be.

    **Objection (Art. 21)** and **automated decision-making (Art. 22)** —
    recorded and assessed. Art. 22 is live here: autoverification is automated
    processing that produces an effect on the subject, so a subject may demand
    human review of any autoverified result, which the override mechanism
    provides.
    """

    class Kind(models.TextChoices):
        ACCESS = "access", "Access (Art. 15)"
        RECTIFICATION = "rectification", "Rectification (Art. 16)"
        ERASURE = "erasure", "Erasure (Art. 17)"
        RESTRICTION = "restriction", "Restriction of processing (Art. 18)"
        PORTABILITY = "portability", "Portability (Art. 20)"
        OBJECTION = "objection", "Objection (Art. 21)"
        HUMAN_REVIEW = "human_review", "Human review of automated decision (Art. 22)"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        IDENTITY_PENDING = "identity_pending", "Awaiting identity verification"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        PARTIALLY_REFUSED = "partially_refused", "Completed in part; partly refused"
        REFUSED = "refused", "Refused"
        WITHDRAWN = "withdrawn", "Withdrawn by the subject"

    #: Art. 12(3): one month, extendable by two further months for complex
    #: requests, provided the subject is told within the first month.
    RESPONSE_DAYS = 30
    EXTENSION_DAYS = 60

    reference = models.CharField(max_length=32, unique=True, help_text="DSR-YYYY-NNNN")
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, related_name="subject_requests"
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)

    received_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField()
    extended = models.BooleanField(default=False)
    extension_reason = models.TextField(blank=True)

    requested_by = models.CharField(
        max_length=255,
        help_text="The subject, or a representative — recorded as given.",
    )
    relationship = models.CharField(
        max_length=64, blank=True,
        help_text="Self, parent, legal guardian, attorney, executor.",
    )
    detail = models.TextField(blank=True, help_text="What the subject actually asked for.")

    #: Art. 12(6): where there is reasonable doubt about identity, further
    #: information may be requested. Acting on an unverified request is how a
    #: laboratory discloses a person's results to someone impersonating them.
    identity_verified = models.BooleanField(default=False)
    identity_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="verified_subject_requests",
    )
    identity_verified_at = models.DateTimeField(null=True, blank=True)
    identity_evidence = models.CharField(
        max_length=255, blank=True, help_text="What was checked, not a copy of it."
    )

    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="handled_subject_requests",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.TextField(blank=True)
    refusal_basis = models.TextField(
        blank=True,
        help_text="The specific legal basis for any refusal — Art. 12(4) requires it.",
    )
    export_path = models.CharField(
        max_length=512, blank=True,
        help_text="Where the encrypted export was written. Never the passphrase.",
    )
    records_erased = models.PositiveIntegerField(default=0)
    signature = models.ForeignKey(
        ElectronicSignature, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="subject_requests",
    )

    objects = DataSubjectRequestQuerySet.as_manager()

    class Meta:
        db_table = "data_subject_requests"
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["status", "due_at"]),
            models.Index(fields=["patient", "-received_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} — {self.get_kind_display()}"

    def save(self, *args, **kwargs):
        if not self.due_at:
            self.due_at = self.received_at + timedelta(days=self.RESPONSE_DAYS)
        super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        return self.status not in (
            self.Status.COMPLETED, self.Status.REFUSED, self.Status.WITHDRAWN
        )

    @property
    def is_overdue(self) -> bool:
        return bool(self.is_open and self.due_at and self.due_at < timezone.now())

    @property
    def days_remaining(self) -> int | None:
        if not self.is_open or not self.due_at:
            return None
        return (self.due_at - timezone.now()).days

    @property
    def is_actionable(self) -> bool:
        """Whether work may proceed: identity established, request still open."""
        return self.is_open and self.identity_verified


class ProcessingRestriction(IdentifiedModel):
    """A record marked under GDPR Art. 18: stored, but otherwise left alone.

    Enforced, not merely noted. A restricted patient's data is excluded from
    research extracts, the public API and outbound webhooks, and any screen
    showing it displays the restriction. Art. 18(2) permits continued storage
    and processing for the establishment or defence of legal claims and for the
    protection of others' rights — which is why it is a flag rather than a
    deletion, and why clinical care is explicitly exempted below.
    """

    patient = models.OneToOneField(
        "patients.Patient", on_delete=models.CASCADE, related_name="processing_restriction"
    )
    request = models.ForeignKey(
        DataSubjectRequest, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="restrictions",
    )
    reason = models.TextField()
    applied_at = models.DateTimeField(default=timezone.now)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="applied_restrictions",
    )
    lifted_at = models.DateTimeField(null=True, blank=True)
    lifted_reason = models.TextField(blank=True)
    #: Art. 18(2) — care continues. A restriction that blocked a clinician from
    #: seeing a result would endanger the subject it exists to protect.
    permits_clinical_care = models.BooleanField(default=True)

    class Meta:
        db_table = "processing_restrictions"
        ordering = ["-applied_at"]

    def __str__(self) -> str:
        return f"restriction on {self.patient_id}"

    @property
    def is_active(self) -> bool:
        return self.lifted_at is None
