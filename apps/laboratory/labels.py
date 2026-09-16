"""Specimen labels: what goes on a tube, and how it reaches a printer.

Two rendering paths, because laboratories have two situations:

* **ZPL**, for the thermal printers laboratories actually use — Zebra and the
  many printers that emulate it. Generated as text and sent to the printer's
  raw TCP port (9100) or written to a spool the print server picks up.
* **HTML/SVG**, for a browser and an ordinary printer. Slower and less
  durable, but it works on day one, on any hardware, with nothing installed —
  which is what a site needs during commissioning and what a small laboratory
  may need permanently.

What goes on the label
----------------------
The minimum that makes a mislabelled tube impossible to mistake for a correct
one: **two patient identifiers** (name and MRN — the Joint Commission's
National Patient Safety Goal 01.01.01 requires two, and the accession number
is not one of them because it identifies the specimen, not the person), the
accession number as text *and* as a barcode, the specimen type, the collection
time, and the additive/tube type so the right tube is drawn.

Nothing is abbreviated to make it fit. A label that has dropped half a surname
to fit the width is how two patients called Smith become one.
"""
from __future__ import annotations

import logging
import socket
from dataclasses import dataclass

from django.utils import timezone

from apps.laboratory.barcodes import svg as barcode_svg

logger = logging.getLogger("dx.labels")

#: Default label stock: 50mm x 25mm at 203dpi, the common tube label.
DEFAULT_WIDTH_DOTS = 400
DEFAULT_HEIGHT_DOTS = 200
PRINTER_PORT = 9100
PRINTER_TIMEOUT = 5


@dataclass(frozen=True)
class Label:
    """Everything that goes on one specimen label."""

    accession_number: str
    patient_name: str
    mrn: str
    date_of_birth: str
    specimen_type: str
    container: str
    collected_at: str
    priority: str = ""
    additive: str = ""
    copy_number: int = 1
    copies_total: int = 1

    @classmethod
    def for_specimen(cls, specimen, *, copy_number: int = 1, copies_total: int = 1):
        order = specimen.order
        patient = order.patient
        return cls(
            accession_number=order.accession_number,
            patient_name=patient.full_name,
            mrn=patient.mrn,
            date_of_birth=patient.dob.strftime("%d/%m/%Y") if patient.dob else "",
            specimen_type=specimen.type or "",
            container=specimen.container_id or order.accession_number,
            collected_at=(
                specimen.collection_date.strftime("%d/%m %H:%M")
                if specimen.collection_date else timezone.now().strftime("%d/%m %H:%M")
            ),
            priority=order.priority or "",
            copy_number=copy_number,
            copies_total=copies_total,
        )

    @property
    def is_urgent(self) -> bool:
        return self.priority in {"STAT", "Urgent"}

    @property
    def copy_marker(self) -> str:
        return f"{self.copy_number}/{self.copies_total}" if self.copies_total > 1 else ""


# ── ZPL ──────────────────────────────────────────────────────────────────────


def _zpl_escape(value: str) -> str:
    """Neutralise ZPL's own control characters.

    A patient called ``^Smith`` would otherwise emit a field command in the
    middle of the label and print something unpredictable — which, on a
    specimen label, is a patient safety problem rather than a cosmetic one.
    """
    return (value or "").replace("^", " ").replace("~", " ").replace("\\", " ")


def zpl(label: Label, *, width: int = DEFAULT_WIDTH_DOTS,
        height: int = DEFAULT_HEIGHT_DOTS, darkness: int = 10) -> str:
    """Render one label as ZPL II.

    Laid out for a 50x25mm tube label at 203dpi. The barcode is Code 128 with
    the human-readable line printed underneath by the printer itself, so a
    scanner failure still leaves something a person can key.
    """
    lines = [
        "^XA",
        f"^MD{darkness}",
        f"^PW{width}",
        f"^LL{height}",
        "^LH0,0",
        "^CI28",  # UTF-8, so a name with an accent prints as its name
        # Patient name — the largest thing on the label, because it is what a
        # person checks against the wristband.
        f"^FO10,8^A0N,26,26^FB{width - 20},1,0,L^FD{_zpl_escape(label.patient_name)}^FS",
        f"^FO10,38^A0N,20,20^FD{_zpl_escape(label.mrn)}  {_zpl_escape(label.date_of_birth)}^FS",
        # Accession as Code 128, with its text beneath.
        f"^FO10,62^BY2,2.5,50^BCN,50,Y,N,N^FD{_zpl_escape(label.accession_number)}^FS",
        f"^FO10,{height - 34}^A0N,18,18^FD{_zpl_escape(label.specimen_type)}"
        f"  {_zpl_escape(label.collected_at)}^FS",
    ]
    if label.additive:
        lines.append(
            f"^FO{width - 130},{height - 34}^A0N,18,18^FD{_zpl_escape(label.additive)}^FS"
        )
    if label.is_urgent:
        # Reversed block: legible across a bench at a glance.
        lines.append(
            f"^FO{width - 90},6^GB80,26,26,B,0^FS"
            f"^FO{width - 84},10^A0N,20,20^FR^FD{_zpl_escape(label.priority)}^FS"
        )
    if label.copy_marker:
        lines.append(
            f"^FO{width - 50},{height - 16}^A0N,14,14^FD{label.copy_marker}^FS"
        )
    lines.append("^XZ")
    return "\n".join(lines)


def zpl_batch(labels) -> str:
    return "\n".join(zpl(label) for label in labels)


def send_to_printer(payload: str, host: str, port: int = PRINTER_PORT,
                    timeout: float = PRINTER_TIMEOUT) -> None:
    """Send raw ZPL to a network printer.

    Raises on failure rather than logging and moving on. A label that silently
    failed to print is a tube that gets hand-written, and hand-written tubes
    are the pre-analytical error every laboratory is trying to remove.
    """
    with socket.create_connection((host, port), timeout=timeout) as connection:
        connection.sendall(payload.encode("utf-8"))
    logger.info("Sent %s bytes of ZPL to %s:%s", len(payload), host, port)


# ── Browser fallback ─────────────────────────────────────────────────────────


def html(labels, *, per_row: int = 2) -> str:
    """Printable label sheet, self-contained, for an ordinary printer."""
    from xml.sax.saxutils import escape

    cells = []
    for label in labels:
        cells.append(f"""
      <div class="label">
        <div class="name">{escape(label.patient_name)}</div>
        <div class="ids">{escape(label.mrn)} &middot; {escape(label.date_of_birth)}</div>
        <div class="code">{barcode_svg(label.accession_number, height=34, module_width=1.1)}</div>
        <div class="meta">
          {escape(label.specimen_type)} &middot; {escape(label.collected_at)}
          {f'<span class="urgent">{escape(label.priority)}</span>' if label.is_urgent else ''}
          {f'<span class="copy">{escape(label.copy_marker)}</span>' if label.copy_marker else ''}
        </div>
      </div>""")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Specimen labels</title>
<style>
 @page {{ margin: 6mm; }}
 body {{ font: 11px/1.3 Arial, sans-serif; margin: 0; }}
 .sheet {{ display: grid; grid-template-columns: repeat({per_row}, 1fr); gap: 3mm; }}
 .label {{ border: 1px dashed #999; padding: 2mm 3mm; height: 25mm;
          overflow: hidden; page-break-inside: avoid; }}
 .name {{ font-size: 13px; font-weight: 700; white-space: nowrap;
         overflow: hidden; text-overflow: ellipsis; }}
 .ids {{ font-size: 11px; }}
 .code svg {{ height: 12mm; }}
 .meta {{ font-size: 10px; }}
 .urgent {{ background: #000; color: #fff; padding: 0 3px; font-weight: 700; }}
 .copy {{ float: right; color: #666; }}
 .noprint {{ margin-bottom: 4mm; }}
 @media print {{ .noprint {{ display: none; }} .label {{ border-color: transparent; }} }}
</style></head><body>
<div class="noprint">
  <button onclick="window.print()">Print</button>
  <span>Check the label against the patient's wristband before drawing.</span>
</div>
<div class="sheet">{''.join(cells)}</div>
</body></html>"""
