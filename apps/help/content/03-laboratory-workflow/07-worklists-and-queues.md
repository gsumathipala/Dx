---
title: Worklists, queues and worksheets
summary: Organising work by stage, by authorisation group and by analytical batch.
audience: scientist, manager
keywords: worklist, queue, worksheet, batch, authorisation, routing, workstation
---

## Three different groupings

Work gets organised three ways, for three reasons.

| Grouping | Groups by | Answers |
| --- | --- | --- |
| **Worklist** | Stage | What needs doing next? |
| **Queues** | Authorisation group | Who is allowed to authorise this? |
| **Worksheets** | Analytical batch | What goes on the analyser together? |

## The worklist

Everything not yet complete, ordered by priority then age. Filter by status or
search. Orders ready for clinical verification carry a checkbox for batch
verification.

## Authorisation queues

A queue segregates work so it reaches the right authoriser. A laboratory might
route endocrinology to one queue and toxicology to another, each with its own
permitted roles.

Configure at **Settings → Authorisation queues**; each has a name, a
department, and the roles permitted to authorise from it. Orders not assigned
to one appear as *Unassigned*.

## Worksheets

A worksheet is a batch for the analyser: a named group of orders and tests run
together, usually with controls and calibrators.

Batching matters because a run shares conditions — the same reagent lot, the
same calibration, the same controls. If QC fails, the worksheet tells you
exactly which patient results are affected.

## Workstations and routing

**Workstations** are benches or analysers. Each declares the tests and specimen
types it handles, its status, and its throughput.

**Routing rules** decide which workstation a test goes to. Where several could
run it, work is balanced by current load — STAT work goes to the shortest
queue, routine work to the least utilised bench.

Keep these current. A retired analyser still marked Online is a queue of work
going nowhere.
