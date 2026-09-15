"""Instrument ingest, FHIR endpoints and the LOINC catalogue."""
from __future__ import annotations

import hmac
import json
import logging

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.common.constants import MANAGEMENT_ROLES, SYSTEM_ROLES
from apps.common.views import DxListView
from apps.interop.models import (
    HostQuery, Icd10Code, InstrumentInterface, InstrumentMessage, LoincCode,
)
from apps.interop.services import diagnostic_report, oru_r01, report_bundle

logger = logging.getLogger("dx.interop")
MANAGERS = tuple(MANAGEMENT_ROLES)
#: Instrument connections are system plumbing, so the installer maintains them.
MANAGERS_AND_INSTALLER = tuple(dict.fromkeys(MANAGERS + tuple(SYSTEM_ROLES)))


class LoincForm(forms.ModelForm):
    class Meta:
        model = LoincCode
        fields = ["loinc_code", "long_name", "short_name", "component", "property",
                  "time_aspect", "system", "scale", "method", "status"]


class InterfaceForm(forms.ModelForm):
    class Meta:
        model = InstrumentInterface
        fields = ["name", "equipment", "protocol", "direction", "host", "port",
                  "enabled", "test_code_map"]
        help_texts = {"test_code_map": 'JSON object mapping instrument codes to Dx test codes'}


# ── Instrument middleware ingest ─────────────────────────────────────────────


@csrf_exempt
@require_POST
def ingest(request):
    """Receive parsed instrument results from the instrument server.

    Authenticated with a shared bearer token rather than a session, because the
    caller is a service. The raw payload is retained as an
    ``InstrumentMessage`` so a disputed result can be traced back to what the
    analyser actually transmitted.
    """
    expected = getattr(settings, "INSTRUMENT_INGEST_TOKEN", "")
    presented = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(presented, expected):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    raw = request.body.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        InstrumentMessage.objects.create(
            raw_payload=raw[:100_000], status=InstrumentMessage.Status.FAILED,
            error=f"Invalid JSON: {error}",
        )
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    interface = InstrumentInterface.objects.filter(pk=payload.get("interface_id")).first()
    message = InstrumentMessage.objects.create(
        interface=interface,
        raw_payload=raw[:100_000],
        parsed_payload=payload,
        accession_number=payload.get("accession"),
        status=InstrumentMessage.Status.PARSED,
    )

    applied, errors = _apply_instrument_results(payload, interface)

    message.results_applied = applied
    message.status = (
        InstrumentMessage.Status.APPLIED if applied
        else InstrumentMessage.Status.FAILED if errors
        else InstrumentMessage.Status.IGNORED
    )
    message.error = "; ".join(errors) if errors else None
    message.save(update_fields=["results_applied", "status", "error"])

    if interface is not None:
        interface.last_message_at = timezone.now()
        interface.save(update_fields=["last_message_at"])

    status_code = 200 if applied or not errors else 422
    return JsonResponse({"applied": applied, "errors": errors}, status=status_code)


def _apply_instrument_results(payload: dict, interface) -> tuple[int, list[str]]:
    """Write instrument results against the matching order."""
    from apps.audit.context import audit_as
    from apps.audit.models import AuditSource
    from apps.laboratory.models import Order, Result, TestDefinition

    accession = payload.get("accession")
    if not accession:
        return 0, ["No accession number in payload"]

    order = Order.objects.filter(accession_number=accession).first()
    if order is None:
        return 0, [f"No order matching accession {accession}"]

    code_map = (interface.test_code_map if interface else {}) or {}
    applied, errors = 0, []

    # Instrument writes are attributed to the interface, never to a person.
    with audit_as(
        actor_username=f"instrument:{interface.name if interface else 'unknown'}",
        actor_role="instrument",
        source=AuditSource.INSTRUMENT,
    ):
        for entry in payload.get("results", []):
            raw_code = entry.get("test_code")
            dx_code = code_map.get(raw_code, raw_code)
            test = TestDefinition.objects.filter(code=dx_code).first()
            if test is None:
                errors.append(f"Unknown test code {raw_code}")
                continue

            result, _ = Result.objects.update_or_create(
                order=order,
                test_key=test.id,
                defaults={
                    "test": test,
                    "value": str(entry.get("value", "")),
                    "status": "Resulted",
                    "entered_by": f"instrument:{interface.name if interface else 'unknown'}",
                },
            )
            result.recompute_flags()
            result.save(update_fields=["result_flags"])
            applied += 1

            # Instrument results go through the same clinical rules as manual entry.
            from apps.clinical.services import run_clinical_engine

            run_clinical_engine(order, test, result, result.entered_by)

    return applied, errors


# ── FHIR / HL7 export ────────────────────────────────────────────────────────


@login_required
def fhir_diagnostic_report(request, pk):
    from apps.laboratory.models import Order

    order = get_object_or_404(
        Order.objects.select_related("patient").prefetch_related("results__test"), pk=pk
    )
    as_bundle = request.GET.get("bundle") == "1"
    payload = report_bundle(order) if as_bundle else diagnostic_report(order)
    return JsonResponse(payload, json_dumps_params={"indent": 2})


@login_required
def hl7_oru(request, pk):
    from apps.laboratory.models import Order

    order = get_object_or_404(
        Order.objects.select_related("patient").prefetch_related("results__test"), pk=pk
    )
    message = oru_r01(order)
    response = HttpResponse(message, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{order.accession_number}.hl7"'
    return response


# ── Catalogue and interface administration ───────────────────────────────────


class InstrumentMessageListView(DxListView):
    """Instrument traffic, with the payload hidden from roles barred from PHI.

    The columns differ by role rather than the values being blanked, so an
    installer is not shown a table of empty cells.
    """

    model = InstrumentMessage
    required_roles = MANAGERS_AND_INSTALLER
    page_title = "Instrument message log"
    search_fields = ["error"]
    filter_fields = {"status": "status"}

    CLINICAL_COLUMNS = [
        ("Received", "received_at", "nowrap"), ("Interface", "interface.name", ""),
        ("Accession", "accession_number", "mono"), ("Status", "status", ""),
        ("Applied", "results_applied", ""), ("Error", "error", "muted"),
    ]
    REDACTED_COLUMNS = [
        ("Received", "received_at", "nowrap"), ("Interface", "interface.name", ""),
        ("Accession", "safe_accession", "muted"), ("Status", "status", ""),
        ("Applied", "results_applied", ""), ("Payload", "safe_payload", "muted"),
        ("Error", "error", "muted"),
    ]

    @property
    def columns(self):
        if self.request.user.may_see_patient_data:
            return self.CLINICAL_COLUMNS
        return self.REDACTED_COLUMNS

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.may_see_patient_data:
            # An accession number is a specimen identifier, so searching for
            # one must not confirm whether it exists.
            queryset = queryset.only(
                "received_at", "interface", "status", "results_applied", "error",
                "raw_payload",
            )
        return queryset


# ── Host query: the analyser asking what to run ──────────────────────────────


@csrf_exempt
@require_POST
def host_query(request):
    """Answer an analyser's query for a specimen's outstanding tests.

    The instrument server translates the analyser's ASTM ``Q`` record or HL7
    ``QBP^Q11`` into this call and translates the answer back, so the LIS does
    not have to speak every analyser's query dialect.
    """
    expected = getattr(settings, "INSTRUMENT_INGEST_TOKEN", "")
    presented = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(presented, expected):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as error:
        return JsonResponse({"error": f"Invalid JSON: {error}"}, status=400)

    identifier = (payload.get("specimen_id") or payload.get("accession") or "").strip()
    if not identifier:
        return JsonResponse({"error": "No specimen identifier in the query."}, status=400)

    interface = InstrumentInterface.objects.filter(pk=payload.get("interface_id")).first()
    if interface is not None and interface.direction != InstrumentInterface.Direction.BIDIRECTIONAL:
        # Answering a query on a unidirectional interface would hand work to an
        # analyser the laboratory has not configured to receive it.
        query = HostQuery.objects.create(
            interface=interface, specimen_identifier=identifier[:64],
            status=HostQuery.Status.REFUSED,
            detail="The interface is configured as unidirectional.",
        )
        return JsonResponse({
            "specimen_id": identifier, "tests": [], "status": query.status,
            "detail": query.detail,
        }, status=409)

    from apps.audit.context import audit_as
    from apps.audit.models import AuditSource
    from apps.interop.query import answer

    with audit_as(
        actor_username=f"instrument:{interface.name if interface else 'unknown'}",
        actor_role="instrument",
        source=AuditSource.INSTRUMENT,
    ):
        query = answer(identifier, interface=interface)

    return JsonResponse({
        "specimen_id": identifier,
        "status": query.status,
        "tests": query.tests,
        "accession": query.order.accession_number if query.order_id else None,
        "patient_id": str(query.order.patient_id) if query.order_id else None,
        "detail": query.detail,
    })


# ── Inbound HL7: orders and patient administration ───────────────────────────


@csrf_exempt
@require_POST
def inbound_hl7(request):
    """Accept an ORM/OML order or an ADT patient message and answer with an ACK.

    The body is the raw HL7 message. Responses are always an HL7 ACK with the
    correct acknowledgement code, because an integration engine parses the ACK
    and will retry forever on anything else.
    """
    expected = getattr(settings, "INSTRUMENT_INGEST_TOKEN", "")
    presented = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(presented, expected):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    raw = request.body.decode("utf-8", errors="replace")
    interface = InstrumentInterface.objects.filter(
        pk=request.headers.get("X-Dx-Interface") or ""
    ).first()

    from apps.audit.context import audit_as
    from apps.audit.models import AuditSource
    from apps.interop.inbound import build_ack, handle

    message = InstrumentMessage.objects.create(
        interface=interface,
        raw_payload=raw[:100_000],
        status=InstrumentMessage.Status.RECEIVED,
    )

    with audit_as(
        actor_username=f"hl7:{interface.name if interface else 'inbound'}",
        actor_role="interface",
        source=AuditSource.INSTRUMENT,
    ):
        code, detail = handle(raw, interface=interface)

    message.parsed_payload = detail
    message.accession_number = detail.get("accession")
    message.status = (
        InstrumentMessage.Status.APPLIED if code == "AA"
        else InstrumentMessage.Status.FAILED
    )
    message.error = detail.get("error")
    message.save(update_fields=["parsed_payload", "accession_number", "status", "error"])

    if code != "AA":
        from apps.operations.exceptions import ExceptionSource, raise_exception

        raise_exception(
            source=ExceptionSource.INBOUND_MESSAGE,
            source_key=f"inbound:{message.pk}",
            title="An inbound HL7 message was refused",
            detail=detail.get("error") or "The message could not be processed.",
            severity="high",
            entity_type="interop.InstrumentMessage",
            entity_id=message.pk,
        )

    ack = build_ack(raw, code, detail)
    status_code = 200 if code == "AA" else 422 if code == "AE" else 400
    return HttpResponse(
        ack, content_type="application/hl7-v2; charset=utf-8", status=status_code
    )


class HostQueryListView(DxListView):
    """The host query log, redacted for roles barred from patient data."""

    model = HostQuery
    required_roles = MANAGERS_AND_INSTALLER
    page_title = "Host query log"
    page_subtitle = "What analysers asked for, and what they were told."
    search_fields = ["specimen_identifier", "detail"]
    filter_fields = {"status": "status", "interface": "interface_id"}

    CLINICAL_COLUMNS = [
        ("Asked", "requested_at", "nowrap"), ("Interface", "interface.name", ""),
        ("Specimen", "specimen_identifier", "mono"), ("Status", "get_status_display", ""),
        ("Tests", "test_count", "right"), ("ms", "response_ms", "right"),
    ]
    REDACTED_COLUMNS = [
        ("Asked", "requested_at", "nowrap"), ("Interface", "interface.name", ""),
        ("Specimen", "safe_identifier", "muted"), ("Status", "get_status_display", ""),
        ("Answer", "safe_tests", "muted"), ("ms", "response_ms", "right"),
    ]

    @property
    def columns(self):
        if self.request.user.may_see_patient_data:
            return self.CLINICAL_COLUMNS
        return self.REDACTED_COLUMNS


class Icd10Form(forms.ModelForm):
    class Meta:
        model = Icd10Code
        fields = ["code", "description", "chapter", "category", "billable",
                  "valid_from", "valid_to"]
