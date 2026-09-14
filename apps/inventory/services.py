"""Reagent consumption and stock control."""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import F

from apps.inventory.models import InventoryItem, InventoryTransaction

logger = logging.getLogger("dx.inventory")


@transaction.atomic
def consume_reagent(test, user_id: str, quantity: int = 1) -> InventoryTransaction | None:
    """Decrement the reagent linked to a test.

    The original matched reagents by substring against the test code, which
    silently consumed the wrong item whenever one code was a prefix of another.
    The link is now an explicit relation, and the decrement uses an atomic
    ``F()`` update so two concurrent result entries cannot both read the same
    starting quantity.
    """
    item = (
        InventoryItem.objects.filter(tests=test)
        .exclude(quantity__lte=0)
        .order_by("expiration_date")
        .first()
    )
    if item is None:
        logger.debug("No reagent linked to test %s — nothing consumed", getattr(test, "code", test))
        return None

    if item.is_expired:
        logger.warning("Reagent %s is expired and was not consumed", item.name)
        return None

    updated = InventoryItem.objects.filter(pk=item.pk, quantity__gte=quantity).update(
        quantity=F("quantity") - quantity
    )
    if not updated:
        logger.warning("Reagent %s went out of stock before consumption", item.name)
        return None

    item.refresh_from_db(fields=["quantity"])
    return InventoryTransaction.objects.create(
        item=item,
        change=-quantity,
        reason="Test usage",
        user_id=user_id,
        balance_after=item.quantity,
    )


@transaction.atomic
def adjust_stock(item: InventoryItem, change: int, reason: str, user_id: str) -> InventoryTransaction:
    """Record a restock or manual correction."""
    InventoryItem.objects.filter(pk=item.pk).update(quantity=F("quantity") + change)
    item.refresh_from_db(fields=["quantity"])
    return InventoryTransaction.objects.create(
        item=item, change=change, reason=reason, user_id=user_id, balance_after=item.quantity
    )


def low_stock_items():
    return InventoryItem.objects.filter(quantity__lte=F("min_threshold")).order_by("quantity")
