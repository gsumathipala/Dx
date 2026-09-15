"""Inbound HL7 v2: order messages and patient administration.

Results flow *in* from analysers; orders and demographics flow in from the
hospital. Until now Dx spoke HL7 outbound only, which meant every order was
keyed by hand even where a hospital order-entry system already held it — the
single largest source of transcription error in a laboratory, and the reason
accession-to-result time is dominated by clerical work in most sites.

Supported messages
------------------
=========== ==========================================================
ORM^O01     New order (ORC NW), cancellation (ORC CA), hold (ORC HD)
OML^O21     Laboratory order, treated identically to ORM^O01
ADT^A01/A04 Admit / register a patient
ADT^A08     Update patient information
ADT^A28/A31 Add / update person information
ADT^A40     Merge patient identifiers
=========== ==========================================================

Everything is answered with an HL7 ACK carrying AA (accepted), AE (application
error — the message was understood and refused) or AR (rejected — the message
could not be understood). A sender that gets AE knows not to retry; one that
gets AR has a malformed message. Conflating the two is why integration
failures take days to diagnose.

Parsing here is deliberately tolerant of field counts and strict about
identity: a message whose patient cannot be resolved is refused rather than
guessed at, because attaching an order to the wrong patient is the worst
outcome a laboratory system can produce.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("dx.interop.inbound")

SEGMENT_SEPARATOR = "\r"


class InboundError(Exception):
    """The message was understood but cannot be acted on (→ ACK AE)."""


class MalformedMessage(Exception):
    """The message could not be parsed at all (→ ACK AR)."""


# ── Field access ─────────────────────────────────────────────────────────────


def _unescape(value: str) -> str:
    """Reverse HL7's escape sequences.

    Skipped by most implementations, which is why a patient called
    O'Brien\\S\\Smith occasionally reaches a laboratory system with a caret in
    the middle of their surname.
    """
    for escape, char in (("\\F\\", "|"), ("\\S\\", "^"), ("\\T\\", "&"),
                         ("\\R\\", "~"), ("\\E\\", "\\")):
        value = value.replace(escape, char)
    return value


@dataclass
class Segment:
    name: str
    fields: list[str] = field(default_factory=list)

    def get(self, index: int, component: int | None = None, default: str = "") -> str:
        """Field ``index`` (1-based, as HL7 numbers them), optionally a component."""
        if index >= len(self.fields):
            return default
        value = self.fields[index]
        if component is not None:
            parts = value.split("^")
            value = parts[component - 1] if len(parts) >= component else ""
        return _unescape(value.strip())


@dataclass
class Message:
    segments: list[Segment]

    def first(self, name: str) -> Segment | None:
        return next((s for s in self.segments if s.name == name), None)

    def all(self, name: str) -> list[Segment]:
        return [s for s in self.segments if s.name == name]

    @property
    def type(self) -> str:
        msh = self.first("MSH")
        if msh is None:
            return ""
        # MSH-9 is message type: ORM^O01. MSH is offset by one because MSH-1 is
        # the field separator itself, which is consumed by splitting.
        return msh.get(8).replace("^", "^")

    @property
    def control_id(self) -> str:
        msh = self.first("MSH")
        return msh.get(9) if msh else ""

    @property
    def sending_application(self) -> str:
        msh = self.first("MSH")
        return msh.get(2) if msh else ""


def parse_message(raw: str) -> Message:
    text = (raw or "").replace("\r\n", "\r").replace("\n", "\r").strip()
    if not text:
        raise MalformedMessage("Empty message.")

    segments = []
    for line in text.split(SEGMENT_SEPARATOR):
        line = line.strip()
        if not line:
            continue
        fields = line.split("|")
        segments.append(Segment(name=fields[0].upper(), fields=fields))

    if not segments or segments[0].name != "MSH":
        raise MalformedMessage("The message does not begin with an MSH segment.")
    return Message(segments=segments)


def parse_hl7_datetime(value: str):
    """HL7 timestamps: YYYYMMDD[HHMM[SS]], optionally with a zone offset."""
    if not value:
        return None
    stamp = re.split(r"[+\-]", value.strip())[0]
    stamp = "".join(character for character in stamp if character.isdigit())

    for length, pattern in ((14, "%Y%m%d%H%M%S"), (12, "%Y%m%d%H%M"), (8, "%Y%m%d")):
        if len(stamp) < length:
            continue
        try:
            parsed = datetime.strptime(stamp[:length], pattern)
        except ValueError:
            continue
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    return None


def parse_hl7_date(value: str):
    parsed = parse_hl7_datetime(value)
    return parsed.date() if parsed else None


# ── Patient resolution ───────────────────────────────────────────────────────

GENDER_MAP = {"M": "M", "F": "F", "O": "O", "U": "U", "A": "O", "N": "U", "": "U"}


def _pid_fields(pid: Segment) -> dict:
    """The demographics Dx stores, from a PID segment."""
    return {
        "mrn": pid.get(3, 1) or pid.get(2, 1),
        "last_name": pid.get(5, 1),
        "first_name": pid.get(5, 2),
        "dob": parse_hl7_date(pid.get(7)),
        "gender": GENDER_MAP.get((pid.get(8) or "U").upper(), "U"),
        "address": ", ".join(part for part in [
            pid.get(11, 1), pid.get(11, 3), pid.get(11, 5)
        ] if part) or None,
        "phone": pid.get(13, 1) or None,
    }


def resolve_or_create_patient(pid: Segment, *, create: bool = True):
    """Find the patient this PID refers to, creating them if permitted.

    Identity is the MRN and nothing else. Matching on name and date of birth
    would merge two different people with the same name and birthday, which
    happens more often than intuition suggests and is unrecoverable once
    results are attached.
    """
    from apps.patients.models import Patient

    data = _pid_fields(pid)
    if not data["mrn"]:
        raise InboundError("The PID segment carries no medical record number (PID-3).")

    existing = Patient.objects.filter(mrn=data["mrn"]).first()
    if existing is not None:
        return existing, False
    if not create:
        raise InboundError(f"No patient with MRN {data['mrn']}.")
    if not data["last_name"]:
        raise InboundError("A new patient needs at least a family name (PID-5).")
    if data["dob"] is None:
        # Age drives reference intervals, critical limits and several rules.
        # Registering a patient without one would silently degrade all three.
        raise InboundError("A new patient needs a date of birth (PID-7).")

    return Patient.objects.create(**data), True


# ── ADT ──────────────────────────────────────────────────────────────────────

#: Trigger events that create or update a patient record.
ADT_UPSERT = {"A01", "A04", "A05", "A08", "A28", "A31"}
#: Trigger events that merge one identifier into another.
ADT_MERGE = {"A40", "A34", "A18"}


@transaction.atomic
def handle_adt(message: Message) -> dict:
    """Register, update or merge a patient."""
    trigger = message.type.split("^")[1] if "^" in message.type else ""
    pid = message.first("PID")
    if pid is None:
        raise MalformedMessage("An ADT message must carry a PID segment.")

    if trigger in ADT_MERGE:
        return _handle_merge(message, pid)
    if trigger not in ADT_UPSERT:
        raise InboundError(f"ADT trigger event {trigger or '(none)'} is not supported.")

    patient, created = resolve_or_create_patient(pid)
    if created:
        return {"action": "created", "patient_id": str(patient.pk), "mrn": patient.mrn}

    data = _pid_fields(pid)
    changed = []
    for attribute, value in data.items():
        if attribute == "mrn" or value in (None, ""):
            continue
        if getattr(patient, attribute) != value:
            setattr(patient, attribute, value)
            changed.append(attribute)
    if changed:
        patient.save(update_fields=changed)

    return {
        "action": "updated" if changed else "unchanged",
        "patient_id": str(patient.pk),
        "mrn": patient.mrn,
        "fields": changed,
    }


def _handle_merge(message: Message, pid: Segment) -> dict:
    """Move records from a superseded MRN onto the surviving one.

    The surviving identifier is in PID-3; the one being retired is in MRG-1.
    Orders, results and everything hanging off them are repointed, and the old
    patient row is kept — not deleted — so that a report issued under the old
    number remains explicable. Deleting it would break the audit trail's
    references, which is precisely what an immutable trail exists to prevent.
    """
    from apps.patients.models import Patient

    mrg = message.first("MRG")
    if mrg is None:
        raise MalformedMessage("A merge message must carry an MRG segment.")

    surviving_mrn = pid.get(3, 1)
    retiring_mrn = mrg.get(1, 1)
    if not surviving_mrn or not retiring_mrn:
        raise InboundError("Both the surviving and the retiring MRN are required.")
    if surviving_mrn == retiring_mrn:
        raise InboundError("The surviving and retiring MRNs are the same.")

    surviving = Patient.objects.filter(mrn=surviving_mrn).first()
    retiring = Patient.objects.filter(mrn=retiring_mrn).first()
    if surviving is None or retiring is None:
        raise InboundError("One of the two patient records does not exist.")

    moved = retiring.orders.update(patient=surviving)
    retiring.merged_into = surviving
    retiring.merged_at = timezone.now()
    retiring.save(update_fields=["merged_into", "merged_at"])

    return {
        "action": "merged",
        "surviving_mrn": surviving_mrn,
        "retiring_mrn": retiring_mrn,
        "orders_moved": moved,
    }


# ── ORM / OML ────────────────────────────────────────────────────────────────

#: ORC-1 order control codes we act on.
ORDER_NEW = {"NW", "SN", "OK"}
ORDER_CANCEL = {"CA", "OC", "CR"}
ORDER_HOLD = {"HD"}

PRIORITY_MAP = {"S": "STAT", "A": "STAT", "R": "Routine", "P": "Urgent", "C": "Urgent"}


@transaction.atomic
def handle_order(message: Message, *, interface=None) -> dict:
    """Accession, cancel or hold an order sent by the hospital.

    Each ORC/OBR pair is one requested battery. Where the hospital sends a
    placer order number we keep it, so a later cancellation for the same
    placer number finds the order we made.
    """
    from apps.common.constants import OrderStatus
    from apps.laboratory.models import Order, TestDefinition
    from apps.laboratory.services import create_order

    pid = message.first("PID")
    if pid is None:
        raise MalformedMessage("An order message must carry a PID segment.")

    orcs = message.all("ORC")
    obrs = message.all("OBR")
    if not orcs and not obrs:
        raise MalformedMessage("The message carries neither an ORC nor an OBR segment.")

    control = (orcs[0].get(1) if orcs else "NW").upper()
    placer = (orcs[0].get(2, 1) if orcs else "") or (obrs[0].get(2, 1) if obrs else "")

    if control in ORDER_CANCEL:
        if not placer:
            raise InboundError("A cancellation needs a placer order number (ORC-2).")
        order = Order.objects.filter(placer_order_number=placer).first()
        if order is None:
            raise InboundError(f"No order with placer number {placer}.")
        if order.status in (OrderStatus.COMPLETED, OrderStatus.CANCELLED):
            return {"action": "ignored", "reason": f"The order is already {order.status}."}
        order.status = OrderStatus.CANCELLED
        order.updated_at = timezone.now()
        order.save(update_fields=["status", "updated_at"])
        return {"action": "cancelled", "accession": order.accession_number}

    if control not in ORDER_NEW:
        raise InboundError(f"Order control code {control} is not supported.")

    if placer and Order.objects.filter(placer_order_number=placer).exists():
        # A retransmitted order must not produce a second specimen.
        existing = Order.objects.get(placer_order_number=placer)
        return {
            "action": "duplicate",
            "accession": existing.accession_number,
            "reason": "An order with this placer number already exists.",
        }

    patient, patient_created = resolve_or_create_patient(pid)

    codes, unknown = [], []
    for obr in obrs:
        # OBR-4 is the universal service identifier: <id>^<text>^<coding system>.
        code = obr.get(4, 1)
        alternate = obr.get(4, 4)
        test = (
            TestDefinition.objects.filter(code=code, active=True).first()
            or TestDefinition.objects.filter(loinc_code=code, active=True).first()
            or (TestDefinition.objects.filter(code=alternate, active=True).first()
                if alternate else None)
        )
        if test is None:
            unknown.append(code or "(blank)")
        else:
            codes.append(test)

    if not codes:
        raise InboundError(
            "None of the requested tests could be matched to the catalogue: "
            + ", ".join(unknown)
        )

    first_obr = obrs[0]
    order = create_order(
        patient=patient,
        tests=codes,
        ordered_by=first_obr.get(16, 2) or first_obr.get(16, 1) or message.sending_application,
        priority=PRIORITY_MAP.get((first_obr.get(5) or "R").upper(), "Routine"),
        specimen_type=first_obr.get(15, 1) or None,
    )
    order.placer_order_number = placer or ""
    order.source_message_id = message.control_id
    if control in ORDER_HOLD:
        order.status = OrderStatus.PENDING
    order.save(update_fields=["placer_order_number", "source_message_id", "status"])

    _attach_diagnoses_from_message(message, order)

    return {
        "action": "created",
        "accession": order.accession_number,
        "patient_created": patient_created,
        "tests": [test.code for test in codes],
        "unmatched_tests": unknown,
    }


def _attach_diagnoses_from_message(message: Message, order) -> None:
    """Take ICD-10 codes from DG1 segments, or from OBR-31 if there are none."""
    from apps.interop.models import Icd10Code
    from apps.laboratory.models import OrderDiagnosis

    entries: list[tuple[str, str]] = []
    for dg1 in message.all("DG1"):
        # DG1-3 is the diagnosis code; DG1-4 a free-text description.
        code = dg1.get(3, 1)
        if code:
            entries.append((code, dg1.get(3, 2) or dg1.get(4)))

    if not entries:
        for obr in message.all("OBR"):
            code = obr.get(31, 1)
            if code:
                entries.append((code, obr.get(31, 2)))

    for rank, (code, description) in enumerate(entries, start=1):
        catalogue = Icd10Code.objects.filter(code=code).first()
        OrderDiagnosis.objects.get_or_create(
            order=order,
            code_value=code,
            defaults={
                "code": catalogue,
                "description": (catalogue.description if catalogue else description) or "",
                "rank": rank,
                "recorded_by": "hl7",
            },
        )


# ── Dispatch and acknowledgement ─────────────────────────────────────────────


HANDLERS = {
    "ORM": handle_order,
    "OML": handle_order,
    "ADT": handle_adt,
}


def handle(raw: str, *, interface=None) -> tuple[str, dict]:
    """Process one inbound message. Returns (ack_code, detail).

    ``ack_code`` is AA, AE or AR. Nothing raises past this boundary — an
    unhandled exception would leave the sender waiting for an acknowledgement
    that never comes, and HL7 senders respond to that by retrying forever.
    """
    try:
        message = parse_message(raw)
    except MalformedMessage as error:
        return "AR", {"error": str(error)}

    kind = message.type.split("^")[0].upper()
    handler = HANDLERS.get(kind)
    if handler is None:
        return "AR", {"error": f"Message type {kind or '(none)'} is not supported."}

    try:
        detail = handler(message) if kind == "ADT" else handler(message, interface=interface)
        return "AA", detail
    except InboundError as error:
        return "AE", {"error": str(error)}
    except MalformedMessage as error:
        return "AR", {"error": str(error)}
    except Exception as error:
        logger.exception("Inbound %s message failed", kind)
        return "AE", {"error": f"The message could not be processed: {error}"}


def build_ack(raw: str, code: str, detail: dict) -> str:
    """An HL7 v2.5 ACK, echoing the sender's control id."""
    control_id = ""
    try:
        control_id = parse_message(raw).control_id
    except MalformedMessage:
        pass

    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    text = (detail.get("error") or detail.get("action") or "").replace("|", " ")[:180]
    return (
        f"MSH|^~\\&|DX|LAB|||{stamp}||ACK|{control_id or stamp}|P|2.5\r"
        f"MSA|{code}|{control_id}|{text}\r"
    )
