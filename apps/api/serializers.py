"""Turning models into the JSON the API promises.

Written as plain functions rather than a serialisation framework. There are
fourteen shapes; a framework would add a dependency, a layer of indirection and
a set of defaults that quietly change what is exposed when a model gains a
field. Here, adding a field to a model exposes nothing until somebody writes it
down — which is the behaviour you want when the fields are patient data.
"""
from __future__ import annotations


def _iso(value):
    return value.isoformat() if value is not None else None


def test_definition(test) -> dict:
    return {
        "code": test.code,
        "name": test.name,
        "department": test.department.name if test.department_id else None,
        "units": test.units,
        "loinc_code": test.loinc_code,
        "methodology": test.methodology,
        "turnaround_target_hours": test.tat_hours,
        "reference_interval": {
            "low": test.normal_low,
            "high": test.normal_high,
            "critical_low": test.panic_low,
            "critical_high": test.panic_high,
        },
        "specimen_types": test.specimen_types or [],
        "active": test.active,
    }


def patient(record, *, identifiers: bool = True) -> dict:
    """A patient. With ``identifiers=False`` only the surrogate id survives.

    The reduced form is what goes into a webhook payload by default: enough for
    a subscriber to call back and fetch the record over an authenticated,
    logged channel, and not enough to identify anybody from the payload alone.
    """
    if not identifiers:
        return {"id": str(record.pk)}
    return {
        "id": str(record.pk),
        "mrn": record.mrn,
        "first_name": record.first_name,
        "last_name": record.last_name,
        "date_of_birth": _iso(record.dob),
        "age": record.age,
        "gender": record.gender,
        "phone": record.phone,
        "email": record.email,
        "address": record.address,
    }


def result(record) -> dict:
    test = record.test
    return {
        "id": str(record.pk),
        "test_code": test.code if test is not None else record.test_key,
        "test_name": test.name if test is not None else None,
        "loinc_code": test.loinc_code if test is not None else None,
        "value": record.value,
        "numeric_value": record.numeric_value,
        "units": test.units if test is not None else None,
        "flags": record.result_flags or [],
        "status": record.status,
        "comments": record.comments,
        "entered_by": record.entered_by,
        "technically_validated_by": record.technical_validated_by,
        "clinically_verified_by": record.clinical_verified_by,
        "autoverified": str(record.clinical_verified_by or "").startswith("rule:"),
        "reported_at": _iso(record.timestamp),
    }


def order(record, *, include_results: bool = False, identifiers: bool = True) -> dict:
    payload = {
        "id": str(record.pk),
        "accession_number": record.accession_number,
        "status": record.status,
        "priority": record.priority,
        "ordered_by": record.order_by,
        "ordered_at": _iso(record.timestamp),
        "completed_at": _iso(record.completed_at),
        "turnaround_hours": record.turnaround_hours,
        "patient": patient(record.patient, identifiers=identifiers) if record.patient_id else None,
        "tests": [test.code for test in record.tests.all()],
        "diagnoses": [
            {"code": diagnosis.code_value, "description": diagnosis.description,
             "rank": diagnosis.rank, "type": diagnosis.kind}
            for diagnosis in record.diagnoses.all()
        ],
    }
    if include_results:
        payload["results"] = [
            result(row) for row in record.results.all() if not row.is_report_row
        ]
        narrative = next((row for row in record.results.all() if row.is_report_row), None)
        payload["narrative"] = narrative.comments if narrative else None
    return payload


def exception_item(record) -> dict:
    return {
        "id": str(record.pk),
        "source": record.source,
        "title": record.title,
        "detail": record.detail,
        "severity": record.severity,
        "status": record.status,
        "accession_number": record.accession,
        "test_code": record.test_code,
        "raised_at": _iso(record.raised_at),
        "due_at": _iso(record.due_at),
        "occurrences": record.occurrences,
        "assigned_to": record.assigned_to.username if record.assigned_to_id else None,
        "resolution": record.resolution,
    }


def webhook(record, *, secret: str | None = None) -> dict:
    payload = {
        "id": str(record.pk),
        "name": record.name,
        "url": record.url,
        "events": record.events or [],
        "active": record.active,
        "include_identifiers": record.include_identifiers,
        "consecutive_failures": record.consecutive_failures,
        "created_at": _iso(record.created_at),
    }
    if secret is not None:
        payload["secret"] = secret
    return payload


def icd10(record) -> dict:
    return {
        "code": record.code,
        "description": record.description,
        "chapter": record.chapter,
        "billable": record.billable,
    }


def loinc(record) -> dict:
    return {
        "loinc_code": record.loinc_code,
        "long_name": record.long_name,
        "short_name": record.short_name,
        "component": record.component,
        "property": record.property,
        "system": record.system,
        "scale": record.scale,
        "method": record.method,
        "status": record.status,
    }
