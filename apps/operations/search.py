"""Cross-application lookup.

A member of staff holding a tube knows one thing: the accession number printed
on it. Before this existed they had to decide which screen that tube belonged
to before they could search for it. This resolves an identifier from anywhere
in the application, and sends an exact match straight to the screen where the
record is actionable *right now* — pending orders to reception, resulted orders
to verification, completed ones to the report.

Barcode scanners type their payload and press Enter, so the same box makes the
application scanner-driven without any scanner-specific code.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q
from django.urls import reverse

from apps.common.constants import OrderStatus

#: Where an order should open, given where it has got to.
ORDER_DESTINATION = {
    OrderStatus.PENDING: "laboratory:receiving",
    OrderStatus.RECEIVED: "laboratory:result_entry",
    OrderStatus.IN_PROGRESS: "laboratory:result_entry",
    OrderStatus.RESULTED: "laboratory:result_entry",
    OrderStatus.TECHNICALLY_VALIDATED: "laboratory:result_entry",
    OrderStatus.CLINICALLY_VERIFIED: "reporting:report_detail",
    OrderStatus.COMPLETED: "reporting:report_detail",
}


@dataclass(frozen=True)
class Hit:
    kind: str
    label: str
    sublabel: str
    url: str
    status: str = ""


def _order_url(order) -> str:
    name = ORDER_DESTINATION.get(order.status, "laboratory:result_entry")
    if name == "laboratory:receiving":
        # Reception has no per-order page; the worklist is the right landing.
        return reverse("laboratory:receiving")
    return reverse(name, args=[order.pk])


def search(query: str, *, limit: int = 8) -> list[Hit]:
    """Find orders and patients matching ``query``.

    Deliberately narrow: an identifier or a name. Anything broader belongs on
    the screen that owns the data, where the filters are.
    """
    from apps.laboratory.models import Order
    from apps.patients.models import Patient

    query = (query or "").strip()
    if len(query) < 2:
        return []

    hits: list[Hit] = []

    orders = (
        Order.objects.filter(
            Q(accession_number__icontains=query) | Q(patient__mrn__icontains=query)
        )
        .select_related("patient")
        .order_by("-timestamp")[:limit]
    )
    for order in orders:
        hits.append(Hit(
            kind="Order",
            label=order.accession_number,
            sublabel=f"{order.patient.full_name} · {order.patient.mrn}",
            url=_order_url(order),
            status=order.status,
        ))

    patients = Patient.objects.filter(
        Q(mrn__icontains=query) | Q(last_name__icontains=query) | Q(first_name__icontains=query)
    ).order_by("last_name")[:limit]
    for patient in patients:
        hits.append(Hit(
            kind="Patient",
            label=patient.full_name,
            sublabel=f"{patient.mrn} · born {patient.dob} · {patient.age_display}",
            url=reverse("patients:detail", args=[patient.pk]),
        ))

    return hits


def resolve_exact(query: str):
    """Return the single destination for an unambiguous identifier, else None.

    A scanned accession number should navigate, not present a list of one.
    """
    from apps.laboratory.models import Order
    from apps.patients.models import Patient

    query = (query or "").strip()
    if not query:
        return None

    order = Order.objects.filter(accession_number__iexact=query).select_related("patient").first()
    if order is not None:
        return _order_url(order)

    patient = Patient.objects.filter(mrn__iexact=query).first()
    if patient is not None:
        return reverse("patients:detail", args=[patient.pk])

    return None
