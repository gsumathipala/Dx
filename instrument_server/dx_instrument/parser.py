"""Decode ASTM E1394 and HL7 v2 result messages into a common shape.

Both protocols are normalised to::

    {
        "accession": "2026-01-02-0001",
        "instrument": "ARCH-1",
        "results": [{"test_code": "GLU", "value": "5.4", "units": "mmol/L",
                     "flags": "N", "completed_at": "20260102101500"}],
    }
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("dx.instrument.parser")


@dataclass
class ParsedMessage:
    accession: str | None = None
    instrument: str | None = None
    patient_id: str | None = None
    results: list[dict] = field(default_factory=list)
    #: Specimen identifiers the analyser is *asking* about rather than
    #: reporting on. An ASTM Q record or an HL7 QBP^Q11 populates this.
    queries: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.results

    @property
    def is_query(self) -> bool:
        return bool(self.queries)

    def as_payload(self, interface_id: str | None = None) -> dict:
        return {
            "interface_id": interface_id,
            "accession": self.accession,
            "instrument": self.instrument,
            "patient_id": self.patient_id,
            "results": self.results,
        }


def _split(record: str, delimiter: str) -> list[str]:
    return record.split(delimiter)


def parse_astm(payload: str) -> ParsedMessage:
    """Parse an ASTM E1394 record stream.

    Record types: H (header), P (patient), O (order), R (result), C (comment),
    L (terminator). Only H, P, O and R carry information we need.
    """
    message = ParsedMessage()

    for record in payload.replace("\r\n", "\r").split("\r"):
        record = record.strip()
        if not record:
            continue

        record_type = record[0].upper()
        fields = _split(record, "|")

        try:
            if record_type == "H" and len(fields) > 4:
                # Sender name sits in the 5th field, sometimes component-delimited.
                message.instrument = fields[4].split("^")[0] or None

            elif record_type == "P" and len(fields) > 3:
                message.patient_id = fields[3] or None

            elif record_type == "O" and len(fields) > 2:
                # O|1|specimen id|instrument specimen id|^^^TEST
                message.accession = (fields[2] or fields[3] if len(fields) > 3 else fields[2]) or None

            elif record_type == "Q" and len(fields) > 2:
                # Q|1|^specimen id^|…  — the analyser asking for a work list.
                # The starting range is in the third field, component 2 in most
                # implementations and component 1 in some, so both are tried.
                parts = [part for part in fields[2].split("^") if part.strip()]
                if parts:
                    message.queries.append(parts[-1].strip())

            elif record_type == "R" and len(fields) > 3:
                # R|1|^^^GLU|5.4|mmol/L|ref|flags|...|status|...|completed
                test_code = fields[2].split("^")[-1] if fields[2] else ""
                if not test_code:
                    continue
                message.results.append({
                    "test_code": test_code,
                    "value": fields[3].strip() if len(fields) > 3 else "",
                    "units": fields[4].strip() if len(fields) > 4 else "",
                    "reference": fields[5].strip() if len(fields) > 5 else "",
                    "flags": fields[6].strip() if len(fields) > 6 else "",
                    "completed_at": fields[12].strip() if len(fields) > 12 else "",
                })
        except IndexError:
            logger.warning("Malformed ASTM record skipped: %r", record[:80])

    return message


def parse_hl7(payload: str) -> ParsedMessage:
    """Parse an HL7 v2 ORU^R01 result message."""
    message = ParsedMessage()

    for segment in payload.replace("\r\n", "\r").replace("\n", "\r").split("\r"):
        segment = segment.strip()
        if not segment:
            continue

        fields = _split(segment, "|")
        segment_type = fields[0].upper()

        try:
            if segment_type == "MSH" and len(fields) > 2:
                message.instrument = fields[2] or None

            elif segment_type == "PID" and len(fields) > 3:
                message.patient_id = fields[3].split("^")[0] or None

            elif segment_type == "OBR" and len(fields) > 3:
                # Filler order number, falling back to the placer order number.
                message.accession = (fields[3] or fields[2] or "").split("^")[0] or None

            elif segment_type == "QPD" and len(fields) > 3:
                # QPD|SLI^Specimen labelling instructions|query id|specimen id
                identifier = fields[3].split("^")[0].strip()
                if identifier:
                    message.queries.append(identifier)

            elif segment_type == "OBX" and len(fields) > 5:
                identifier = fields[3].split("^") if len(fields) > 3 else []
                # Prefer the local code over the coding-system identifier.
                test_code = identifier[0] if identifier else ""
                if len(identifier) >= 4 and identifier[3]:
                    test_code = identifier[3]
                if not test_code:
                    continue
                message.results.append({
                    "test_code": test_code,
                    "value": fields[5].strip(),
                    "units": fields[6].strip() if len(fields) > 6 else "",
                    "reference": fields[7].strip() if len(fields) > 7 else "",
                    "flags": fields[8].strip() if len(fields) > 8 else "",
                    "completed_at": fields[14].strip() if len(fields) > 14 else "",
                })
        except IndexError:
            logger.warning("Malformed HL7 segment skipped: %r", segment[:80])

    return message


def parse(payload: str, protocol: str) -> ParsedMessage:
    if protocol == "hl7":
        return parse_hl7(payload)
    return parse_astm(payload)
