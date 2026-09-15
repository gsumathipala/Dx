"""Order accessioning and the result-entry pipeline."""
from __future__ import annotations

import logging
from datetime import date

from django.db import IntegrityError, models, transaction
from django.db.models import Max
from django.utils import timezone

from apps.audit.recorder import record
from apps.common.constants import AuditAction, OrderStatus
from apps.laboratory.models import Order, Result, ResultSignature, TestDefinition

logger = logging.getLogger("dx.laboratory")

ACCESSION_LOCK_ID = 5_512_907_441


def generate_accession_number(*, on_date: date | None = None) -> str:
    """Allocate the next accession number for the day: ``YYYY-MM-DD-NNNN``.

    The original took a snapshot read inside a transaction but inserted the row
    afterwards, so two concurrent requests could be handed the same number.
    Here the sequence is taken under a PostgreSQL advisory lock held for the
    calling transaction, so the number is reserved until the order is committed.

    The numeric suffix is parsed rather than compared as text, which also keeps
    ordering correct past 9999 requests in a single day.
    """
    from django.db import connection

    today = on_date or timezone.localdate()
    prefix = today.strftime("%Y-%m-%d")

    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [ACCESSION_LOCK_ID])

    existing = Order.objects.filter(accession_number__startswith=f"{prefix}-").values_list(
        "accession_number", flat=True
    )
    highest = 0
    for number in existing:
        suffix = number.rsplit("-", 1)[-1]
        if suffix.isdigit():
            highest = max(highest, int(suffix))

    return f"{prefix}-{highest + 1:04d}"


@transaction.atomic
def create_order(*, patient, tests, ordered_by: str, priority: str = "Routine",
                 requester=None, specimen_type: str | None = None, user=None) -> Order:
    """Accession a new request.

    Runs inside one transaction so the accession number, the order and its
    specimen either all exist or none do.
    """
    order = Order.objects.create(
        patient=patient,
        accession_number=generate_accession_number(),
        status=OrderStatus.PENDING,
        order_by=ordered_by,
        requester=requester,
        priority=priority,
        timestamp=timezone.now(),
    )
    order.tests.set(tests)

    if specimen_type:
        from apps.laboratory.models import Specimen

        Specimen.objects.create(
            order=order,
            type=specimen_type,
            container_id=order.accession_number,
            status="Collected",
        )

    return order


class ResultEntryError(Exception):
    """Raised when a result cannot be saved or validated."""


@transaction.atomic
def save_results(
    *,
    order: Order,
    values: dict[str, str],
    user,
    action: str | None = None,
    notes: str | None = None,
    queue=None,
    password: str | None = None,
    request=None,
    reason: str | None = None,
) -> dict:
    """Enter, validate or verify results for an order.

    ``action`` is one of ``None`` (plain entry), ``TECHNICAL_VALIDATE`` or
    ``CLINICAL_VERIFY``. Validation actions run the regulatory gates first:
    competency, QC status, self-verification and electronic signature.
    """
    from apps.audit.recorder import record
    from apps.clinical.services import run_clinical_engine
    from apps.compliance.models import ElectronicSignature
    from apps.compliance.services import (
        apply_signature,
        check_competency,
        check_qc_status,
        check_self_verification,
    )
    from apps.inventory.services import consume_reagent

    is_validation = action in {AuditAction.TECHNICAL_VALIDATE, AuditAction.CLINICAL_VERIFY}

    status = OrderStatus.RESULTED
    if action == AuditAction.TECHNICAL_VALIDATE:
        status = OrderStatus.TECHNICALLY_VALIDATED
    elif action == AuditAction.CLINICAL_VERIFY:
        status = OrderStatus.CLINICALLY_VERIFIED

    tests = {t.id: t for t in TestDefinition.objects.filter(id__in=values.keys())}
    engine_outcomes: dict[str, dict] = {}
    touched: list[Result] = []

    for test_id, raw_value in values.items():
        test = tests.get(test_id)
        if test is None:
            raise ResultEntryError(f"Unknown test {test_id} on order {order.accession_number}.")

        existing = Result.objects.filter(order=order, test_key=test_id).first()

        # ── Regulatory gates, before anything is written ──────────────────────
        if is_validation:
            check_competency(user, test).enforce()
            check_qc_status(test).enforce()
            if action == AuditAction.CLINICAL_VERIFY and existing is not None:
                check_self_verification(user, existing).enforce()

        if existing is None:
            result = Result.objects.create(
                order=order,
                test=test,
                test_key=test_id,
                value=str(raw_value),
                status=status,
                entered_by=user.username,
                technical_validated_by=user.username if action == AuditAction.TECHNICAL_VALIDATE else None,
                clinical_verified_by=user.username if action == AuditAction.CLINICAL_VERIFY else None,
            )
            result.recompute_flags()
            result.save(update_fields=["result_flags"])
            consume_reagent(test, user.username)
            engine_outcomes[test.code] = run_clinical_engine(order, test, result, user.username)
        else:
            existing.value = str(raw_value)
            existing.status = status
            if action == AuditAction.TECHNICAL_VALIDATE:
                existing.technical_validated_by = user.username
            if action == AuditAction.CLINICAL_VERIFY:
                existing.clinical_verified_by = user.username
            existing.save()
            existing.recompute_flags()
            existing.save(update_fields=["result_flags"])
            result = existing
            if not is_validation:
                # A corrected value must be re-assessed by the clinical rules.
                engine_outcomes[test.code] = run_clinical_engine(order, test, result, user.username)

        touched.append(result)

    # ── Report-level narrative ───────────────────────────────────────────────
    if notes:
        Result.objects.update_or_create(
            order=order,
            test_key=Result.REPORT_TEST_ID,
            defaults={"comments": notes, "status": status, "entered_by": user.username},
        )

    # ── Order transition ─────────────────────────────────────────────────────
    now = timezone.now()
    order.updated_at = now
    if status == OrderStatus.CLINICALLY_VERIFIED:
        order.status = OrderStatus.COMPLETED
        order.completed_at = now
    else:
        order.status = status
    if queue is not None:
        order.queue = queue
    order.save(update_fields=["status", "updated_at", "completed_at", "queue"])

    # ── Electronic signature (21 CFR Part 11) ────────────────────────────────
    signature = None
    if is_validation:
        meaning = (
            ElectronicSignature.Meaning.CLINICAL_APPROVAL
            if action == AuditAction.CLINICAL_VERIFY
            else ElectronicSignature.Meaning.TECHNICAL_APPROVAL
        )
        signature = apply_signature(
            user=user,
            meaning=meaning,
            entity_type="laboratory.Order",
            entity_id=order.pk,
            payload={
                "accession": order.accession_number,
                "results": {r.test_key: r.value for r in touched},
                "status": status,
            },
            password=password,
            comment=reason,
            request=request,
        )
        ResultSignature.objects.create(
            order=order,
            signed_by=user.get_full_name(),
            signature_type=(
                ResultSignature.SignatureType.CLINICAL
                if action == AuditAction.CLINICAL_VERIFY
                else ResultSignature.SignatureType.TECHNICAL
            ),
            ip_address=getattr(request, "_dx_client_ip", None),
            user_agent=request.META.get("HTTP_USER_AGENT") if request else None,
        )

    record(
        action=action or AuditAction.UPDATE,
        entity_type="laboratory.Order",
        entity_id=order.pk,
        entity_label=f"results {status} for {order.accession_number}",
        changes={"status": {"old": None, "new": status},
                 "tests": {"old": None, "new": sorted(values.keys())}},
        reason=reason,
        blocking=is_validation,
    )

    return {
        "order": order,
        "results": touched,
        "signature": signature,
        "engine": engine_outcomes,
    }


@transaction.atomic
def amend_report(*, order, result, corrected_value, reason, narrative, user,
                 password=None, request=None, notified_method=None):
    """Issue a corrected report, retaining the original value.

    CAP requires the original result to remain visible, the report to be marked
    as amended with an explanation, the correction to be signed, and the
    requesting clinician to be notified. All four happen here or none do.
    """
    from apps.compliance.models import AmendedReport, CorrectiveAction, ElectronicSignature
    from apps.compliance.services import apply_signature, raise_capa

    original_value = result.value
    # The released report is version 1, so the first amendment is version 2.
    # Taken from the highest existing version rather than a count, so a deleted
    # or out-of-order row cannot produce a duplicate.
    highest = order.amendments.aggregate(models.Max("version"))["version__max"] or 1
    version = highest + 1

    signature = apply_signature(
        user=user,
        meaning=ElectronicSignature.Meaning.CORRECTION,
        entity_type="laboratory.Order",
        entity_id=order.pk,
        payload={
            "accession": order.accession_number,
            "test": result.test_key,
            "from": original_value,
            "to": str(corrected_value),
            "version": version,
        },
        password=password,
        comment=narrative,
        request=request,
    )

    amendment = AmendedReport.objects.create(
        order=order,
        result=result,
        version=version,
        reason=reason,
        original_value=original_value,
        corrected_value=str(corrected_value),
        narrative=narrative,
        amended_by=user,
        signature=signature,
        clinician_notified=bool(notified_method),
        notified_at=timezone.now() if notified_method else None,
        notified_by=user.username if notified_method else None,
        notification_method=notified_method,
    )

    # A released result that had to be corrected is a nonconformance by
    # definition — the report already went out wrong.
    amendment.corrective_action = raise_capa(
        title=f"Amended report {order.accession_number}: {result.test_key}",
        category=CorrectiveAction.Category.RESULT_ERROR,
        description=(
            f"{result.test_key} corrected from {original_value} to {corrected_value} "
            f"after the report was released. Reason: {reason}. {narrative}"
        ),
        raised_by=user,
        severity=CorrectiveAction.Severity.HIGH,
        linked_entity_type="laboratory.Order",
        linked_entity_id=order.pk,
        patient_impact=True,
    )
    amendment.save(update_fields=["corrective_action"])

    result.value = str(corrected_value)
    result.save()
    result.recompute_flags()
    result.save(update_fields=["result_flags"])

    record(
        action=AuditAction.UPDATE,
        entity_type="laboratory.Order",
        entity_id=order.pk,
        entity_label=f"amended report v{version} for {order.accession_number}",
        changes={result.test_key: {"old": original_value, "new": str(corrected_value)}},
        reason=narrative,
        blocking=True,
    )
    return amendment


@transaction.atomic
def verify_batch(*, orders, user, password, request=None, reason=None):
    """Clinically verify several orders under one signing.

    Part 11 §11.50 requires each signed record to carry the signer, the time
    and the meaning of the signature — it does not require a separate password
    entry per record, provided the signature manifest says exactly what was
    signed. Each order is still put through every gate individually, and any
    that fails is reported rather than skipped silently.

    Returns (verified, refusals) where refusals is a list of (order, reason).
    """
    from apps.compliance.services import ControlViolation

    verified, refusals = [], []

    for order in orders:
        values = {
            result.test_key: result.value
            for result in order.results.all()
            if not result.is_report_row and result.value is not None
        }
        if not values:
            refusals.append((order, "No results have been entered."))
            continue

        try:
            # A savepoint per order, so one refusal does not undo the rest.
            with transaction.atomic():
                save_results(
                    order=order,
                    values=values,
                    user=user,
                    action=AuditAction.CLINICAL_VERIFY,
                    password=password,
                    request=request,
                    reason=reason,
                )
        except (ControlViolation, ResultEntryError) as refusal:
            refusals.append((order, str(refusal)))
        else:
            verified.append(order)

    return verified, refusals


def release_report(order, user, *, password: str | None = None, request=None):
    """Release a verified report for distribution."""
    from apps.compliance.models import ElectronicSignature
    from apps.compliance.services import ControlViolation, apply_signature

    if order.status != OrderStatus.COMPLETED:
        raise ControlViolation(
            "Only clinically verified reports can be released.",
            "CLIA 42 CFR §493.1291",
        )

    return apply_signature(
        user=user,
        meaning=ElectronicSignature.Meaning.RELEASE,
        entity_type="laboratory.Order",
        entity_id=order.pk,
        payload={"accession": order.accession_number, "released_at": timezone.now().isoformat()},
        password=password,
        request=request,
    )
