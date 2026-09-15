"""Carrying out data subject requests.

The hard part of GDPR in a clinical laboratory is not the export. It is
knowing, per record, whether erasure is lawful — and being able to say so in
writing when it is not. :func:`assess_erasure` does that against the
laboratory's own retention schedule rather than against a hard-coded rule,
because retention periods differ by jurisdiction and the schedule is where the
laboratory already records its decision.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.constants import AuditAction

logger = logging.getLogger("dx.compliance.subject_rights")


def next_reference() -> str:
    """DSR-YYYY-NNNN, sequential within the year."""
    from apps.compliance.models import DataSubjectRequest

    year = timezone.now().year
    prefix = f"DSR-{year}-"
    highest = 0
    for reference in DataSubjectRequest.objects.filter(
        reference__startswith=prefix
    ).values_list("reference", flat=True):
        suffix = reference.rsplit("-", 1)[-1]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:04d}"


@transaction.atomic
def receive(*, patient, kind: str, requested_by: str, detail: str = "",
            relationship: str = "self", user=None):
    """Log a request. The clock starts now, whether or not identity is verified.

    Art. 12(3) runs from receipt, not from verification — a laboratory cannot
    extend its own deadline by being slow to check who is asking.
    """
    from apps.audit.recorder import record
    from apps.compliance.models import DataSubjectRequest

    request = DataSubjectRequest.objects.create(
        reference=next_reference(),
        patient=patient,
        kind=kind,
        requested_by=requested_by,
        relationship=relationship,
        detail=detail,
        handled_by=user,
        due_at=timezone.now() + timedelta(days=DataSubjectRequest.RESPONSE_DAYS),
        status=DataSubjectRequest.Status.IDENTITY_PENDING,
    )

    record(
        action=AuditAction.CREATE,
        entity_type="compliance.DataSubjectRequest",
        entity_id=request.pk,
        entity_label=f"{request.reference}: {request.get_kind_display()}",
        reason=detail or None,
        blocking=True,
    )
    return request


def verify_identity(request, *, user, evidence: str):
    """Record that the requester is who they say they are."""
    from apps.compliance.models import DataSubjectRequest
    from apps.compliance.services import ControlViolation

    if not (evidence or "").strip():
        raise ControlViolation(
            "Record what was checked before acting on a data subject request.",
            "GDPR Article 12(6)",
        )

    request.identity_verified = True
    request.identity_verified_by = user
    request.identity_verified_at = timezone.now()
    request.identity_evidence = evidence.strip()[:255]
    if request.status == DataSubjectRequest.Status.IDENTITY_PENDING:
        request.status = DataSubjectRequest.Status.IN_PROGRESS
    request.save(update_fields=[
        "identity_verified", "identity_verified_by", "identity_verified_at",
        "identity_evidence", "status",
    ])
    return request


def extend(request, *, reason: str):
    """Take the Art. 12(3) two-month extension, with its reason recorded."""
    from apps.compliance.models import DataSubjectRequest
    from apps.compliance.services import ControlViolation

    if request.extended:
        raise ControlViolation("This request has already been extended once.")
    if not (reason or "").strip():
        raise ControlViolation(
            "The subject must be told why the response is being extended.",
            "GDPR Article 12(3)",
        )

    request.extended = True
    request.extension_reason = reason.strip()
    request.due_at = request.due_at + timedelta(days=DataSubjectRequest.EXTENSION_DAYS)
    request.save(update_fields=["extended", "extension_reason", "due_at"])
    return request


# ── Art. 15 / 20: access and portability ─────────────────────────────────────


def build_export(patient, *, portable: bool = False) -> dict:
    """Everything held about one patient.

    ``portable=True`` renders it as a FHIR R4 Bundle for Art. 20; otherwise a
    fuller Dx-native document including the disclosure accounting, which FHIR
    has no natural place for but Art. 15(1)(c) explicitly requires.
    """
    from apps.compliance.models import DisclosureAccounting, PHIAccessLog
    from apps.interop.services import patient_resource, report_bundle
    from apps.laboratory.models import Order

    orders = (
        Order.objects.filter(patient=patient)
        .select_related("requester")
        .prefetch_related("results__test", "tests", "diagnoses")
        .order_by("timestamp")
    )

    if portable:
        entries = [{"resource": patient_resource(patient)}]
        for order in orders:
            bundle = report_bundle(order)
            entries.extend(
                entry for entry in bundle["entry"]
                if entry["resource"]["resourceType"] != "Patient"
            )
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": timezone.now().isoformat(),
            "entry": entries,
        }

    return {
        "generated_at": timezone.now().isoformat(),
        "article": "GDPR Article 15 — right of access by the data subject",
        "subject": {
            "id": str(patient.pk),
            "mrn": patient.mrn,
            "name": patient.full_name,
            "date_of_birth": patient.dob.isoformat() if patient.dob else None,
            "gender": patient.gender,
            "contact": {"phone": patient.phone, "email": patient.email,
                        "address": patient.address},
        },
        "purposes_of_processing": [
            "Provision of laboratory diagnostic services requested by a clinician",
            "Quality assurance and accreditation of those services",
            "Statutory notification of specified conditions to public health",
            "Billing for services provided",
        ],
        "retention": (
            "Records are retained for the periods set out in the laboratory's "
            "retention schedule, which reflects CLIA 42 CFR §493.1105 and local "
            "statutory requirements."
        ),
        "orders": [
            {
                "accession_number": order.accession_number,
                "ordered_at": order.timestamp.isoformat() if order.timestamp else None,
                "ordered_by": order.order_by,
                "status": order.status,
                "priority": order.priority,
                "diagnoses": [
                    {"code": diagnosis.code_value, "description": diagnosis.description}
                    for diagnosis in order.diagnoses.all()
                ],
                "results": [
                    {
                        "test": result.test.name if result.test_id else result.test_key,
                        "code": result.test.code if result.test_id else result.test_key,
                        "value": result.value,
                        "units": result.test.units if result.test_id else None,
                        "flags": result.result_flags or [],
                        "comments": result.comments,
                        "reported_at": result.timestamp.isoformat() if result.timestamp else None,
                        "verified_by": result.clinical_verified_by,
                        "automated": str(result.clinical_verified_by or "").startswith("rule:"),
                    }
                    for result in order.results.all() if not result.is_report_row
                ],
            }
            for order in orders
        ],
        "disclosures": [
            {
                "disclosed_at": disclosure.disclosed_at.isoformat(),
                "recipient": disclosure.recipient_name,
                "purpose": disclosure.get_purpose_display(),
                "information": disclosure.description,
            }
            for disclosure in DisclosureAccounting.objects.filter(patient=patient)
        ],
        "internal_accesses": PHIAccessLog.objects.filter(patient=patient).count(),
        "automated_decision_making": {
            "in_use": True,
            "description": (
                "Results may be released automatically by a configured decision "
                "rule when they are numeric, within the reference interval, "
                "not flagged, not delta-flagged, backed by in-control quality "
                "control, and on an analyte the laboratory has approved for "
                "automatic release. Any such release can be reviewed by a "
                "person on request (Article 22(3))."
            ),
            "results_released_automatically": sum(
                1 for order in orders for result in order.results.all()
                if str(result.clinical_verified_by or "").startswith("rule:")
            ),
        },
    }


def write_export(request, *, passphrase: str, directory: Path | None = None) -> Path:
    """Write the export to disk, encrypted.

    An Art. 15 export is the most concentrated collection of one person's
    health data the laboratory will ever produce. Writing it in the clear, to
    be emailed or copied onto a stick, would undo every control the system
    enforces internally, so it is always AES-256-GCM encrypted and the
    passphrase is never stored alongside it.
    """
    from apps.compliance.encryption import encrypt_bytes

    portable = request.kind == request.Kind.PORTABILITY
    document = build_export(request.patient, portable=portable)
    body = json.dumps(document, indent=2, default=str).encode("utf-8")

    directory = directory or Path(
        getattr(settings, "SUBJECT_REQUEST_EXPORT_DIR", settings.MEDIA_ROOT / "subject-requests")
    )
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{request.reference}.json.dxenc"
    destination.write_bytes(encrypt_bytes(body, passphrase))

    request.export_path = str(destination)
    request.save(update_fields=["export_path"])
    return destination


# ── Art. 17: erasure ─────────────────────────────────────────────────────────


@dataclass
class ErasureAssessment:
    """What can lawfully be erased for one subject, and what cannot."""

    erasable_orders: list = field(default_factory=list)
    retained_orders: list = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def fully_erasable(self) -> bool:
        return bool(self.erasable_orders) and not self.retained_orders

    @property
    def wholly_refused(self) -> bool:
        return not self.erasable_orders

    @property
    def summary(self) -> str:
        return (
            f"{len(self.erasable_orders)} order(s) past retention and erasable; "
            f"{len(self.retained_orders)} retained."
        )


def retention_days_for(order) -> tuple[int, str]:
    """How long this order's records must be kept, and on what authority.

    Read from the laboratory's own retention schedule where one covers the
    record class, falling back to the CLIA floor. The fallback is deliberately
    the *longest* of the CLIA minima rather than the shortest — erring towards
    keeping a record is recoverable; erring towards deleting one is not.
    """
    from apps.compliance.models import RetentionSchedule

    schedule = (
        RetentionSchedule.objects.filter(
            active=True, record_class=RetentionSchedule.RecordClass.TEST_RECORD
        ).first()
        or RetentionSchedule.objects.filter(active=True).order_by("-retention_years").first()
    )
    if schedule is not None:
        return schedule.retention_years * 365, (
            f"the laboratory's retention schedule for "
            f"{schedule.get_record_class_display().lower()} "
            f"({schedule.retention_years} years, {schedule.citation or 'local policy'})"
        )
    return 10 * 365, "CLIA 42 CFR §493.1105 (pathology reports, ten years)"


def assess_erasure(patient) -> ErasureAssessment:
    """Decide, order by order, whether erasure is lawful."""
    from apps.laboratory.models import Order

    assessment = ErasureAssessment()
    now = timezone.now()

    for order in Order.objects.filter(patient=patient).order_by("timestamp"):
        days, authority = retention_days_for(order)
        reference = order.completed_at or order.timestamp
        expires = reference + timedelta(days=days) if reference else None

        if expires is not None and expires <= now:
            assessment.erasable_orders.append(order)
        else:
            assessment.retained_orders.append(order)
            assessment.reasons.append(
                f"{order.accession_number}: retained until {expires:%Y-%m-%d} under {authority}."
            )

    if assessment.retained_orders:
        assessment.reasons.insert(0, (
            "Erasure is refused for the records listed below. GDPR Article "
            "17(3)(b) disapplies the right to erasure where processing is "
            "necessary for compliance with a legal obligation, and Article "
            "17(3)(c) where it is necessary for reasons of public interest in "
            "the area of public health. Retaining laboratory records for their "
            "statutory period is both."
        ))
    if not assessment.erasable_orders and not assessment.retained_orders:
        assessment.reasons.append("No laboratory records are held for this subject.")

    return assessment


@transaction.atomic
def perform_erasure(request, *, user) -> ErasureAssessment:
    """Erase what may lawfully be erased; record the refusal for the rest.

    Erasure here means the clinical content is destroyed and the shell of the
    record is retained: accession number, dates and the fact of erasure. A
    dangling foreign key would corrupt the audit chain's references, and an
    audit trail that can be broken by a deletion request is not an audit trail.
    """
    from apps.audit.recorder import record
    from apps.compliance.models import DataSubjectRequest
    from apps.compliance.services import ControlViolation

    if not request.identity_verified:
        raise ControlViolation(
            "Verify the requester's identity before erasing anything.",
            "GDPR Article 12(6)",
        )

    assessment = assess_erasure(request.patient)
    erased = 0

    for order in assessment.erasable_orders:
        for result in order.results.all():
            result.value = None
            result.numeric_value = None
            result.comments = "[erased at the data subject's request]"
            result.result_flags = []
            result.save()
            erased += 1
        order.order_by = "[erased]"
        order.save(update_fields=["order_by"])

    if assessment.fully_erasable or not assessment.retained_orders:
        # Nothing clinical remains that requires the identifiers.
        patient = request.patient
        patient.first_name = "[erased]"
        patient.last_name = "[erased]"
        patient.email = None
        patient.phone = None
        patient.address = None
        patient.save(update_fields=[
            "first_name", "last_name", "email", "phone", "address",
        ])

    request.records_erased = erased
    request.outcome = assessment.summary
    request.refusal_basis = "\n".join(assessment.reasons) if assessment.retained_orders else ""
    request.status = (
        DataSubjectRequest.Status.COMPLETED if assessment.fully_erasable
        else DataSubjectRequest.Status.REFUSED if assessment.wholly_refused
        else DataSubjectRequest.Status.PARTIALLY_REFUSED
    )
    request.completed_at = timezone.now()
    request.handled_by = user
    request.save(update_fields=[
        "records_erased", "outcome", "refusal_basis", "status", "completed_at", "handled_by",
    ])

    record(
        action=AuditAction.DELETE,
        entity_type="compliance.DataSubjectRequest",
        entity_id=request.pk,
        entity_label=f"{request.reference}: erasure — {assessment.summary}",
        changes={"records_erased": {"old": 0, "new": erased}},
        reason=request.refusal_basis or "Erasure performed in full.",
        blocking=True,
    )
    return assessment


# ── Art. 18: restriction ─────────────────────────────────────────────────────


@transaction.atomic
def restrict(patient, *, reason: str, user=None, request=None):
    from apps.compliance.models import ProcessingRestriction

    restriction, created = ProcessingRestriction.objects.get_or_create(
        patient=patient,
        defaults={"reason": reason, "applied_by": user, "request": request},
    )
    if not created and restriction.lifted_at is not None:
        restriction.lifted_at = None
        restriction.lifted_reason = ""
        restriction.reason = reason
        restriction.applied_at = timezone.now()
        restriction.applied_by = user
        restriction.save(update_fields=[
            "lifted_at", "lifted_reason", "reason", "applied_at", "applied_by",
        ])
    return restriction


def lift(restriction, *, reason: str, user=None):
    restriction.lifted_at = timezone.now()
    restriction.lifted_reason = reason
    restriction.save(update_fields=["lifted_at", "lifted_reason"])
    return restriction


def is_restricted(patient_id) -> bool:
    """Whether a patient's data is under an active Art. 18 restriction."""
    from apps.compliance.models import ProcessingRestriction

    return ProcessingRestriction.objects.filter(
        patient_id=patient_id, lifted_at__isnull=True
    ).exists()
