---
title: The exception queue
summary: One screen for everything in the laboratory that needs a person, and how to work it.
audience: scientist, medic, manager, clerk
keywords: exceptions, queue, backlog, nonconformance, ISO 15189 8.7, tutorial
---

## What it is for

Before this existed, the things that need attention were spread over eight
screens:

* rejected specimens, on receiving
* unacknowledged critical values, on the clinical screen
* breached turnaround, on the TAT report
* failed QC, on quality
* failed instrument messages, in the interface log
* refused inbound orders, nowhere in particular
* failing integrations, in a log
* amended reports, on compliance

Each was watched by whoever remembered to watch it, which is another way of
saying some were not watched at all.

The exception queue is all of them, on one screen, ordered by how much they
matter.

## How it is ordered

**Severity first, then age.** A critical value that has sat unacknowledged for
forty minutes comes before a webhook that has been failing for a day,
regardless of which was raised first.

## What appears on it

| Source | Raised when |
| --- | --- |
| Specimen rejected | At reception |
| Critical value unacknowledged | Past its escalation deadline without documented read-back |
| Turnaround breached | A target is exceeded |
| Quality control failure | A run fails Westgard |
| Instrument message failed | A payload could not be applied |
| Instrument interface silent | An enabled interface sends nothing for over an hour |
| Inbound message refused | An HL7 order or ADT could not be processed |
| Webhook failing | Delivery gave up after six attempts |
| Raised by a decision rule | A rule with a *raise exception* action fired |
| Report amended | A released report was corrected |
| Data subject request overdue | Past its statutory deadline |

Some of these are **pushed** — raised the moment something goes wrong. Others
are **swept**: a background pass looks for conditions nobody is present to
notice, like a critical value that quietly passed its deadline at 3am.

## Tutorial: work the queue

### 1. Open it

**Exceptions** in the sidebar. The counters across the top show open total,
overdue total, and a breakdown by source — click one to filter.

### 2. Take something

Open an item and press **Acknowledge and take it**. It is now assigned to you
and shows as acknowledged. The clock keeps running; acknowledging is not
closing.

Use the **Mine** filter afterwards to see what you have taken.

### 3. Fix the actual problem

The item tells you what and where. A failed QC item names the analyte and the
rule violated; an instrument message item carries the parse error; a critical
value item names the accession and the value.

### 4. Close it

Press **Close** and write **what was done**.

A note is mandatory. "Resolved" on its own tells the next inspector nothing,
and tells the next person to meet the same fault nothing at all. Write the
sentence you would want to find:

> Control lot 4471 had been left at room temperature overnight. Discarded,
> opened a fresh vial, repeated QC — in control. Fridge temperature log checked
> and normal.

**Tick *raise a corrective action*** for anything with patient impact or a
likely recurrence. That opens a CAPA linked to this item.

**Dismiss instead of resolve** when the item did not represent a real problem.
Both close it; the distinction stays visible afterwards, and a queue full of
dismissals is itself information — it usually means a threshold needs tuning.

## Recurrence

The same underlying problem seen twice does **not** create a second row. The
occurrence count goes up.

A problem that comes back after being closed **reopens the same item**, with
its history intact. So a flaky analyser interface is one item with a count of
forty-three, not forty-three items — which makes it visible as a pattern rather
than as noise.

## Why closing is recorded

ISO 15189 §8.7 requires nonconformities to be *managed*, not merely noticed.
Because every closure carries a note, the queue doubles as the record of what
the laboratory actually dealt with — which is the evidence an assessor asks
for.

## What the installer sees

Nothing. The queue names accession numbers and carries clinical detail, so the
installer role is refused it entirely. Someone maintaining the system can see
that an interface is silent from the interface list, which carries no patient
content.
