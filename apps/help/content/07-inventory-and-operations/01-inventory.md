---
title: Inventory and reagents
summary: Tracking reagent stock, expiry, lot numbers, and why consumption is recorded automatically.
audience: scientist, manager
keywords: inventory, reagent, stock, lot, expiry, consumables, restock
---

## What is tracked

**Inventory** lists reagents and consumables with lot number, expiry, quantity,
unit, minimum threshold and location. Items at or below threshold are flagged on
the dashboard.

## Why lot numbers matter

A lot number is how you answer *"which patients were affected?"* when a reagent
turns out to be faulty.

Manufacturers issue recalls. Lots occasionally have a bias that only appears
once they are in use. Without lot tracking, a recall means reviewing everything
run in a date range — and probably repeating far more than necessary.

Lot numbers also explain step changes. A shift on a Levey-Jennings chart the
morning a new lot was opened is almost always the lot, not the instrument.

## Expiry

An expired reagent is not marginally worse — its performance is simply no longer
guaranteed, and QC may not detect a slow deterioration.

Dx will **not consume an expired reagent** and will not decrement it. Check
expiry when restocking, and use oldest-first.

## Automatic consumption

When a result is entered for a test linked to a reagent, one unit is decremented
and a stock movement is recorded.

The link is explicit — a reagent is associated with the tests it serves.

> An earlier implementation matched reagents by *substring* against the test
> code, which silently consumed the wrong item whenever one code was a prefix of
> another: `GLU` matched a reagent intended for `GLUC2`. Explicit linking
> removes the guesswork.

Consumption is atomic, so two results entered simultaneously cannot both
decrement from the same starting count.

## Adjusting stock

**Adjust** on an item records a movement with a reason: a delivery, a
stocktake correction, breakage, disposal.

Record adjustments as they happen. Stock that drifts from reality is worse than
no stock record, because people trust it.

## Thresholds

Set the minimum threshold to cover your **lead time** — how long a replacement
takes to arrive — plus a margin for a busy week. A threshold of 10 is useless if
delivery takes three weeks and you use 5 a day.

## In-house manufacturing

Laboratories that make their own media or reagents use **Recipes** and
**Production runs**.

A production run moves through Scheduled → In progress → Quarantine → Released.
**Quarantine** is the important state: in-house product is held until its
quality check passes. Dx will not let a batch be released until `qc_passed` is
true.

That mirrors how a manufacturer treats its own product, and for the same
reason — a bad batch of media affects every culture it touches.
