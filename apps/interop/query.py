"""Answering an analyser's question: what should I run on this tube?

Kept separate from the HTTP layer so the same logic serves the middleware
endpoint, a future direct MLLP listener, and the tests, without any of them
having to construct a request.
"""
from __future__ import annotations

import logging
import time

from django.db.models import Q
from django.utils import timezone

from apps.common.constants import OrderStatus

logger = logging.getLogger("dx.interop.query")

#: Statuses at which a specimen still has work to do. A completed or cancelled
#: order returns nothing rather than being re-run — an analyser that re-runs a
#: verified result silently overwrites a report somebody has already acted on.
OPEN_STATUSES = (
    OrderStatus.PENDING, OrderStatus.IN_PROGRESS, OrderStatus.RECEIVED,
    OrderStatus.RESULTED, OrderStatus.TECHNICALLY_VALIDATED,
)


def resolve_order(identifier: str):
    """Find the order an analyser's barcode refers to.

    Analysers variously read the accession number or the container id printed
    on the tube, and different sites label differently. Both are tried, most
    specific first. An aliquot is itself a specimen, so a daughter tube's
    barcode resolves through the same container lookup.
    """
    from apps.laboratory.models import Order, Specimen

    identifier = (identifier or "").strip()
    if not identifier:
        return None

    order = Order.objects.filter(accession_number=identifier).first()
    if order is not None:
        return order

    specimen = Specimen.objects.filter(
        Q(container_id=identifier) | Q(pk=identifier)
    ).select_related("order").first()
    return specimen.order if specimen is not None else None


def outstanding_tests(order, *, interface=None) -> list[str]:
    """Which tests on this order still need running, in the analyser's codes.

    A test that already has a result is not returned. Where the interface has a
    code map, the mapping is inverted so the analyser is answered in its own
    vocabulary rather than in ours — an analyser cannot be expected to know
    what a Dx test code means.
    """
    already = {
        result.test_key for result in order.results.all()
        if result.value not in (None, "")
    }
    wanted = [test for test in order.tests.all() if test.id not in already]

    if interface is None or not interface.test_code_map:
        return [test.code for test in wanted]

    # test_code_map is instrument code → Dx code; answering needs the reverse.
    reverse = {dx: instrument for instrument, dx in (interface.test_code_map or {}).items()}
    return [reverse.get(test.code, test.code) for test in wanted]


def answer(identifier: str, *, interface=None):
    """Resolve a query and record it. Returns the HostQuery row."""
    from apps.interop.models import HostQuery

    started = time.monotonic()
    order = resolve_order(identifier)

    if order is None:
        status, tests, detail = HostQuery.Status.NOT_FOUND, [], (
            f"No order, specimen or aliquot matches {identifier!r}."
        )
    elif order.status not in OPEN_STATUSES:
        status, tests, detail = HostQuery.Status.NO_WORK, [], (
            f"The order is {order.status}; nothing further is expected from the analyser."
        )
    else:
        tests = outstanding_tests(order, interface=interface)
        if tests:
            status, detail = HostQuery.Status.ANSWERED, ""
        else:
            status, detail = HostQuery.Status.NO_WORK, "Every test on the order already has a result."

    query = HostQuery.objects.create(
        interface=interface,
        specimen_identifier=(identifier or "")[:64],
        order=order,
        status=status,
        tests=tests,
        detail=detail,
        response_ms=int((time.monotonic() - started) * 1000),
    )

    if order is not None and status == HostQuery.Status.ANSWERED:
        # Being asked about a specimen means it reached the analyser. That is
        # the earliest reliable signal that a sample is in analysis, and it is
        # more accurate than anyone remembering to press a button.
        if order.status in (OrderStatus.PENDING, OrderStatus.RECEIVED):
            order.status = OrderStatus.IN_PROGRESS
            order.updated_at = timezone.now()
            order.save(update_fields=["status", "updated_at"])

    if interface is not None:
        interface.last_message_at = timezone.now()
        interface.save(update_fields=["last_message_at"])

    return query
