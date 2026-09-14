"""Interoperability: FHIR resource construction and HL7 v2 message building."""
from __future__ import annotations

from django.utils import timezone

FHIR_GENDER = {"M": "male", "F": "female", "O": "other", "U": "unknown"}

#: LOINC interpretation codes for result flags.
INTERPRETATION = {
    "Normal": ("N", "Normal"),
    "Low": ("L", "Low"),
    "High": ("H", "High"),
    "Critical Low": ("LL", "Critically low"),
    "Critical High": ("HH", "Critically high"),
    "Abnormal": ("A", "Abnormal"),
}


def patient_resource(patient) -> dict:
    """FHIR R4 Patient."""
    return {
        "resourceType": "Patient",
        "id": str(patient.pk),
        "identifier": [{
            "system": "urn:dx:mrn",
            "value": patient.mrn,
            "type": {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                "code": "MR", "display": "Medical record number",
            }]},
        }],
        "name": [{"use": "official", "family": patient.last_name, "given": [patient.first_name]}],
        "gender": FHIR_GENDER.get(patient.gender, "unknown"),
        "birthDate": patient.dob.isoformat() if patient.dob else None,
        "telecom": [t for t in (
            {"system": "phone", "value": patient.phone} if patient.phone else None,
            {"system": "email", "value": patient.email} if patient.email else None,
        ) if t],
    }


def observation_resource(result) -> dict:
    """FHIR R4 Observation for a single analyte result."""
    test = result.test
    coding = []
    if test is not None:
        if test.loinc_code:
            coding.append({"system": "http://loinc.org", "code": test.loinc_code, "display": test.name})
        coding.append({"system": "urn:dx:test", "code": test.code, "display": test.name})

    observation = {
        "resourceType": "Observation",
        "id": str(result.pk),
        "status": "final" if result.clinical_verified_by else "preliminary",
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "laboratory", "display": "Laboratory",
        }]}],
        "code": {"coding": coding, "text": test.name if test else result.test_key},
        "subject": {"reference": f"Patient/{result.order.patient_id}"},
        "effectiveDateTime": result.timestamp.isoformat(),
        "issued": result.timestamp.isoformat(),
    }

    if result.numeric_value is not None:
        observation["valueQuantity"] = {
            "value": result.numeric_value,
            "unit": (test.units if test else None) or "",
            "system": "http://unitsofmeasure.org",
        }
    else:
        observation["valueString"] = result.value or ""

    for flag in result.result_flags or []:
        code, display = INTERPRETATION.get(flag, ("A", flag))
        observation.setdefault("interpretation", []).append({"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
            "code": code, "display": display,
        }]})

    if test is not None and (test.normal_low is not None or test.normal_high is not None):
        reference = {}
        if test.normal_low is not None:
            reference["low"] = {"value": test.normal_low, "unit": test.units or ""}
        if test.normal_high is not None:
            reference["high"] = {"value": test.normal_high, "unit": test.units or ""}
        observation["referenceRange"] = [reference]

    return observation


def diagnostic_report(order) -> dict:
    """FHIR R4 DiagnosticReport bundling an order's results."""
    analytes = [r for r in order.results.all() if not r.is_report_row]
    narrative = next((r for r in order.results.all() if r.is_report_row), None)

    return {
        "resourceType": "DiagnosticReport",
        "id": str(order.pk),
        "identifier": [{"system": "urn:dx:accession", "value": order.accession_number}],
        "status": "final" if order.is_complete else "partial",
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
            "code": "LAB", "display": "Laboratory",
        }]}],
        "code": {"text": "Laboratory report"},
        "subject": {"reference": f"Patient/{order.patient_id}"},
        "effectiveDateTime": order.timestamp.isoformat(),
        "issued": (order.completed_at or order.timestamp).isoformat(),
        "result": [{"reference": f"Observation/{r.pk}"} for r in analytes],
        "conclusion": narrative.comments if narrative else None,
    }


def report_bundle(order) -> dict:
    """A self-contained FHIR Bundle: patient, report and observations."""
    analytes = [r for r in order.results.all() if not r.is_report_row]
    entries = [
        {"resource": patient_resource(order.patient)},
        {"resource": diagnostic_report(order)},
    ] + [{"resource": observation_resource(r)} for r in analytes]

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": timezone.now().isoformat(),
        "entry": entries,
    }


# ── HL7 v2 ───────────────────────────────────────────────────────────────────

FIELD = "|"
COMPONENT = "^"
SEGMENT = "\r"


def _escape(value) -> str:
    """Escape HL7 delimiters so data cannot break the message structure."""
    if value is None:
        return ""
    text = str(value)
    for char, escape in (("\\", "\\E\\"), ("|", "\\F\\"), ("^", "\\S\\"),
                         ("&", "\\T\\"), ("~", "\\R\\")):
        text = text.replace(char, escape)
    return text


def oru_r01(order, *, sending_app: str = "DX", sending_facility: str = "LAB") -> str:
    """Build an HL7 v2.5 ORU^R01 result message for an order."""
    now = timezone.now().strftime("%Y%m%d%H%M%S")
    patient = order.patient
    analytes = [r for r in order.results.all() if not r.is_report_row]

    segments = [
        FIELD.join([
            "MSH", "^~\\&", sending_app, sending_facility, "", "", now, "",
            "ORU^R01", _escape(order.accession_number), "P", "2.5",
        ]),
        FIELD.join([
            "PID", "1", "", _escape(patient.mrn), "",
            COMPONENT.join([_escape(patient.last_name), _escape(patient.first_name)]),
            "", patient.dob.strftime("%Y%m%d") if patient.dob else "",
            _escape(patient.gender),
        ]),
        FIELD.join([
            "OBR", "1", _escape(order.accession_number), "", "^Laboratory report",
            _escape(order.priority), "", order.timestamp.strftime("%Y%m%d%H%M%S"),
            "", "", "", "", "", "", "", "", _escape(order.order_by or ""),
        ]),
    ]

    for index, result in enumerate(analytes, start=1):
        test = result.test
        observation_id = COMPONENT.join([
            _escape(test.loinc_code or test.code) if test else _escape(result.test_key),
            _escape(test.name) if test else "",
            "LN" if test and test.loinc_code else "L",
        ])
        abnormal = ""
        if result.result_flags:
            abnormal = INTERPRETATION.get(result.result_flags[0], ("A", ""))[0]

        reference = ""
        if test is not None and test.normal_low is not None and test.normal_high is not None:
            reference = f"{test.normal_low:g}-{test.normal_high:g}"

        segments.append(FIELD.join([
            "OBX", str(index),
            "NM" if result.numeric_value is not None else "ST",
            observation_id, "1", _escape(result.value),
            _escape(test.units if test else ""), reference, abnormal, "", "",
            "F" if result.clinical_verified_by else "P", "", "",
            result.timestamp.strftime("%Y%m%d%H%M%S"),
        ]))

    return SEGMENT.join(segments) + SEGMENT
