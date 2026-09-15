"""The versioned JSON API.

Conventions, all documented in ``docs/API.md``:

* Every response is JSON. Errors are ``{"error": {"code", "message"}}`` with a
  stable ``code`` — clients branch on the code, never on the prose.
* Collections are paginated with ``?page=`` and ``?page_size=`` and return
  ``{"data": [...], "page": {...}}``.
* Times are ISO 8601 with an offset. Dates are ISO 8601 dates.
* Writes are idempotent where the domain allows it, and never partially apply:
  a request either produces a complete record or changes nothing.
"""
from __future__ import annotations

import json
import logging

from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_http_methods

from apps.api import serializers
from apps.api.auth import ApiError, require
from apps.api.models import Scope, Webhook

logger = logging.getLogger("dx.api")

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


# ── Helpers ──────────────────────────────────────────────────────────────────


def _body(request) -> dict:
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ApiError(400, "invalid_json", f"The request body is not valid JSON: {error}")
    if not isinstance(payload, dict):
        raise ApiError(400, "invalid_body", "The request body must be a JSON object.")
    return payload


def _required(payload: dict, *names: str) -> list:
    missing = [name for name in names if not payload.get(name)]
    if missing:
        raise ApiError(
            422, "missing_fields", f"Required field(s) missing: {', '.join(missing)}.",
            fields=missing,
        )
    return [payload[name] for name in names]


def _page(request, queryset, serialise) -> JsonResponse:
    try:
        size = min(int(request.GET.get("page_size", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        number = int(request.GET.get("page", 1))
    except ValueError:
        raise ApiError(400, "invalid_pagination", "page and page_size must be integers.")
    if size < 1 or number < 1:
        raise ApiError(400, "invalid_pagination", "page and page_size must be positive.")

    paginator = Paginator(queryset, size)
    try:
        page = paginator.page(number)
    except EmptyPage:
        return JsonResponse({"data": [], "page": {
            "number": number, "size": size, "total_pages": paginator.num_pages,
            "total_items": paginator.count, "has_next": False,
        }})

    return JsonResponse({
        "data": [serialise(item) for item in page.object_list],
        "page": {
            "number": page.number,
            "size": size,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
            "has_next": page.has_next(),
        },
    })


def _since(request):
    raw = request.GET.get("since")
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is None:
        raise ApiError(400, "invalid_since", "'since' must be an ISO 8601 timestamp.")
    return parsed


# ── Discovery ────────────────────────────────────────────────────────────────


@require(Scope.CATALOGUE_READ)
@require_http_methods(["GET"])
def root(request):
    """What this token can do, and where everything lives."""
    client = request.api_client
    return JsonResponse({
        "service": "Dx Clinical Laboratory Information System",
        "api_version": "v1",
        "server_time": timezone.now().isoformat(),
        "client": {"name": client.name, "scopes": client.scopes or []},
        "endpoints": {
            "tests": "/api/v1/tests/",
            "icd10": "/api/v1/icd10/",
            "loinc": "/api/v1/loinc/",
            "patients": "/api/v1/patients/",
            "orders": "/api/v1/orders/",
            "order_results": "/api/v1/orders/{id}/results/",
            "order_report": "/api/v1/orders/{id}/report/?format=json|fhir|hl7",
            "exceptions": "/api/v1/exceptions/",
            "webhooks": "/api/v1/webhooks/",
        },
        "documentation": "/help/interoperability/the-rest-api/",
    })


# ── Catalogue and terminology ────────────────────────────────────────────────


@require(Scope.CATALOGUE_READ)
@require_http_methods(["GET"])
def tests(request):
    from apps.laboratory.models import TestDefinition

    queryset = TestDefinition.objects.select_related("department").order_by("code")
    if request.GET.get("department"):
        queryset = queryset.filter(department__name=request.GET["department"])
    if request.GET.get("q"):
        queryset = queryset.filter(name__icontains=request.GET["q"])
    if request.GET.get("active") in {"1", "true"}:
        queryset = queryset.filter(active=True)
    return _page(request, queryset, serializers.test_definition)


@require(Scope.CATALOGUE_READ)
@require_http_methods(["GET"])
def icd10(request):
    from apps.interop.models import Icd10Code

    queryset = Icd10Code.objects.order_by("code")
    query = request.GET.get("q")
    if query:
        from django.db.models import Q

        queryset = queryset.filter(Q(code__istartswith=query) | Q(description__icontains=query))
    if request.GET.get("billable") in {"1", "true"}:
        queryset = queryset.filter(billable=True)
    return _page(request, queryset, serializers.icd10)


@require(Scope.CATALOGUE_READ)
@require_http_methods(["GET"])
def loinc(request):
    from apps.interop.models import LoincCode

    queryset = LoincCode.objects.order_by("loinc_code")
    query = request.GET.get("q")
    if query:
        from django.db.models import Q

        queryset = queryset.filter(Q(loinc_code__istartswith=query) | Q(long_name__icontains=query))
    return _page(request, queryset, serializers.loinc)


# ── Patients ─────────────────────────────────────────────────────────────────


@require(Scope.PATIENTS_READ, phi=True)
@require_http_methods(["GET"])
def patients(request):
    from django.db.models import Q

    from apps.patients.models import Patient

    queryset = Patient.objects.order_by("last_name", "first_name")
    if request.GET.get("mrn"):
        queryset = queryset.filter(mrn=request.GET["mrn"])
    query = request.GET.get("q")
    if query:
        queryset = queryset.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(mrn__icontains=query)
        )
    return _page(request, queryset, serializers.patient)


@require(Scope.PATIENTS_READ, phi=True)
@require_http_methods(["GET"])
def patient_detail(request, pk):
    from apps.patients.models import Patient

    record = Patient.objects.filter(pk=pk).first()
    if record is None:
        raise ApiError(404, "not_found", "No such patient.")
    request.api_patient_id = record.pk
    request.api_patient_mrn = record.mrn
    return JsonResponse(serializers.patient(record))


@require(Scope.PATIENTS_WRITE, phi=True)
@require_http_methods(["POST"])
def patient_create(request):
    """Register a patient, or return the existing one with that MRN.

    Registering the same MRN twice is not an error — an integration retrying a
    timed-out request must not produce a duplicate patient. The response says
    which happened via ``created``.
    """
    from apps.patients.models import Patient

    payload = _body(request)
    mrn, first_name, last_name, _dob = _required(
        payload, "mrn", "first_name", "last_name", "date_of_birth"
    )

    existing = Patient.objects.filter(mrn=mrn).first()
    if existing is not None:
        request.api_patient_id = existing.pk
        request.api_patient_mrn = existing.mrn
        return JsonResponse(
            {"created": False, **serializers.patient(existing)}, status=200
        )

    # Parsed rather than passed through: an unparsed string reaches the
    # serialiser as a string and blows up there, several layers from the cause.
    # Age also drives reference intervals and critical limits, so a wrong date
    # is not a cosmetic problem.
    dob = parse_date(str(payload["date_of_birth"]))
    if dob is None:
        raise ApiError(
            422, "invalid_date", "date_of_birth must be an ISO 8601 date (YYYY-MM-DD)."
        )

    record = Patient.objects.create(
        mrn=mrn,
        first_name=first_name,
        last_name=last_name,
        dob=dob,
        gender=payload.get("gender") or "U",
        phone=payload.get("phone") or None,
        email=payload.get("email") or None,
        address=payload.get("address") or None,
    )
    request.api_patient_id = record.pk
    request.api_patient_mrn = record.mrn
    return JsonResponse({"created": True, **serializers.patient(record)}, status=201)


# ── Orders ───────────────────────────────────────────────────────────────────


def _order_queryset():
    from apps.laboratory.models import Order

    return (
        Order.objects.select_related("patient")
        .prefetch_related("tests", "diagnoses")
        .order_by("-timestamp")
    )


@require(Scope.ORDERS_READ, phi=True)
@require_http_methods(["GET"])
def orders(request):
    queryset = _order_queryset()
    if request.GET.get("status"):
        queryset = queryset.filter(status=request.GET["status"])
    if request.GET.get("patient"):
        queryset = queryset.filter(patient_id=request.GET["patient"])
    if request.GET.get("mrn"):
        queryset = queryset.filter(patient__mrn=request.GET["mrn"])
    since = _since(request)
    if since is not None:
        queryset = queryset.filter(timestamp__gte=since)
    return _page(request, queryset, serializers.order)


@require(Scope.ORDERS_READ, phi=True)
@require_http_methods(["GET"])
def order_detail(request, pk):
    record = _order_queryset().prefetch_related("results__test").filter(pk=pk).first()
    if record is None:
        raise ApiError(404, "not_found", "No such order.")
    request.api_patient_id = record.patient_id
    return JsonResponse(serializers.order(record, include_results=True))


@require(Scope.ORDERS_WRITE, phi=True)
@require_http_methods(["POST"])
def order_create(request):
    """Place an order. Either the whole order is created or none of it is."""
    from apps.laboratory.models import TestDefinition
    from apps.laboratory.services import create_order
    from apps.patients.models import Patient

    payload = _body(request)
    test_codes = payload.get("tests") or []
    if not isinstance(test_codes, list) or not test_codes:
        raise ApiError(422, "missing_fields", "'tests' must be a non-empty list of test codes.")

    patient_id, mrn = payload.get("patient_id"), payload.get("mrn")
    if not patient_id and not mrn:
        raise ApiError(422, "missing_fields", "Supply either 'patient_id' or 'mrn'.")

    record = (
        Patient.objects.filter(pk=patient_id).first() if patient_id
        else Patient.objects.filter(mrn=mrn).first()
    )
    if record is None:
        raise ApiError(404, "patient_not_found", "No patient matches that identifier.")

    found = list(TestDefinition.objects.filter(code__in=test_codes, active=True))
    unknown = sorted(set(test_codes) - {test.code for test in found})
    if unknown:
        raise ApiError(
            422, "unknown_tests", f"Unknown or inactive test code(s): {', '.join(unknown)}.",
            codes=unknown,
        )

    with transaction.atomic():
        created = create_order(
            patient=record,
            tests=found,
            ordered_by=payload.get("ordered_by") or request.api_client.name,
            priority=payload.get("priority") or "Routine",
            specimen_type=payload.get("specimen_type"),
        )
        _attach_diagnoses(created, payload.get("diagnoses") or [])

    request.api_patient_id = record.pk
    request.api_patient_mrn = record.mrn
    created = _order_queryset().get(pk=created.pk)
    return JsonResponse(serializers.order(created), status=201)


def _attach_diagnoses(order, diagnoses) -> None:
    """Attach ICD-10 diagnoses to a new order, rejecting unknown codes."""
    from apps.interop.models import Icd10Code
    from apps.laboratory.models import OrderDiagnosis

    for rank, entry in enumerate(diagnoses, start=1):
        code = entry.get("code") if isinstance(entry, dict) else entry
        if not code:
            continue
        catalogue = Icd10Code.objects.filter(code=code).first()
        if catalogue is None:
            raise ApiError(422, "unknown_diagnosis", f"Unknown ICD-10 code {code}.")
        OrderDiagnosis.objects.create(
            order=order,
            code=catalogue,
            code_value=catalogue.code,
            description=catalogue.description,
            rank=rank,
            kind=(entry.get("type") if isinstance(entry, dict) else None)
            or OrderDiagnosis.Kind.WORKING,
        )


@require(Scope.RESULTS_READ, phi=True)
@require_http_methods(["GET"])
def order_results(request, pk):
    from apps.laboratory.models import Order

    record = (
        Order.objects.select_related("patient")
        .prefetch_related("results__test").filter(pk=pk).first()
    )
    if record is None:
        raise ApiError(404, "not_found", "No such order.")
    request.api_patient_id = record.patient_id

    rows = [row for row in record.results.all() if not row.is_report_row]
    if request.GET.get("verified_only") in {"1", "true"}:
        rows = [row for row in rows if row.clinical_verified_by]
    return JsonResponse({"data": [serializers.result(row) for row in rows]})


@require(Scope.REPORTS_READ, phi=True)
@require_http_methods(["GET"])
def order_report(request, pk):
    """The report in whichever representation the caller asked for."""
    from apps.interop.services import oru_r01, report_bundle
    from apps.laboratory.models import Order

    record = (
        Order.objects.select_related("patient")
        .prefetch_related("results__test", "tests", "diagnoses").filter(pk=pk).first()
    )
    if record is None:
        raise ApiError(404, "not_found", "No such order.")
    request.api_patient_id = record.patient_id

    representation = (request.GET.get("format") or "json").lower()
    if representation == "fhir":
        return JsonResponse(report_bundle(record), json_dumps_params={"indent": 2})
    if representation == "hl7":
        return HttpResponse(oru_r01(record), content_type="text/plain; charset=utf-8")
    if representation != "json":
        raise ApiError(400, "invalid_format", "format must be one of json, fhir, hl7.")
    return JsonResponse(serializers.order(record, include_results=True))


# ── Exception queue ──────────────────────────────────────────────────────────


@require(Scope.EXCEPTIONS_READ, phi=True)
@require_http_methods(["GET"])
def exceptions(request):
    from apps.operations.models import ExceptionItem

    queryset = ExceptionItem.objects.select_related("order", "assigned_to")
    if request.GET.get("status") == "open" or not request.GET.get("status"):
        queryset = queryset.open()
    elif request.GET.get("status") != "all":
        queryset = queryset.filter(status=request.GET["status"])
    if request.GET.get("source"):
        queryset = queryset.filter(source=request.GET["source"])
    if request.GET.get("severity"):
        queryset = queryset.filter(severity=request.GET["severity"])
    return _page(request, queryset.order_by("-raised_at"), serializers.exception_item)


# ── Webhooks ─────────────────────────────────────────────────────────────────


@require(Scope.WEBHOOKS_MANAGE)
@require_http_methods(["GET", "POST"])
def webhooks(request):
    if request.method == "GET":
        queryset = Webhook.objects.filter(client=request.api_client).order_by("name")
        return _page(request, queryset, serializers.webhook)

    payload = _body(request)
    name, url = _required(payload, "name", "url")
    events = payload.get("events") or []

    valid = {choice.value for choice in Webhook.Event}
    unknown = [event for event in events if event not in valid]
    if not events or unknown:
        raise ApiError(
            422, "invalid_events",
            "Subscribe to at least one known event."
            + (f" Unknown: {', '.join(unknown)}." if unknown else ""),
            known=sorted(valid),
        )
    if not str(url).startswith("https://"):
        raise ApiError(
            422, "insecure_url",
            "Webhook URLs must use HTTPS. Event payloads can carry patient data.",
        )

    record = Webhook.objects.create(
        name=name, url=url, events=events, client=request.api_client,
        include_identifiers=bool(payload.get("include_identifiers")),
    )
    # The signing secret is shown once, here. Losing it means rotating it.
    return JsonResponse(serializers.webhook(record, secret=record.secret), status=201)


@require(Scope.WEBHOOKS_MANAGE)
@require_http_methods(["GET", "DELETE"])
def webhook_detail(request, pk):
    record = Webhook.objects.filter(pk=pk, client=request.api_client).first()
    if record is None:
        raise ApiError(404, "not_found", "No such webhook.")
    if request.method == "DELETE":
        record.delete()
        return JsonResponse({"deleted": True}, status=200)
    return JsonResponse(serializers.webhook(record))
