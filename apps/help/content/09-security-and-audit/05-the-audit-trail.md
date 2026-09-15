---
title: The audit trail
summary: What is recorded, how to read it, and why it cannot be altered by anyone.
audience: everyone
keywords: audit, trail, log, history, immutable, hash chain, part 11, 11.10
---

## What it records

Every change to anything, everywhere in the system: who, when, what the value
was before, and what it became.

| Recorded | Detail |
| --- | --- |
| Position | Sequence number in the chain |
| When | Event time, and when it reached the trail |
| Who | Username, role, and their id |
| What | Record type, record id, and a readable label |
| Action | Create, update, delete, login, validate, verify, release, restore |
| Changes | Every field that changed, before and after |
| Reason | Where the workflow required one |
| Where from | Web, API, instrument, system, migration, command line |
| Address | IP address, user agent, request id, session |
| Integrity | The previous entry's hash, and this entry's |

> **21 CFR Part 11 §11.10(e)** requires secure, computer-generated,
> time-stamped audit trails that record operator entries and actions creating,
> modifying or deleting records, retain previous values, and remain available
> for review.

## Capture is automatic

Nobody writes to the trail. It is captured by the system as changes happen, so
there is no way to perform an action without recording it — and no way for a
developer to add a feature that quietly escapes it.

The single exception is bulk database operations, which Django performs without
signals. Anything in Dx that writes in bulk records its own summary entry
instead.

## Reading it

**Audit Trail** lists events newest first. Filter by record type, action, user
or date, or search.

Open an entry for the field-level before and after, the actor, the address and
the chain position. **Record history** from there shows everything that ever
happened to that record.

Any list screen has a **History** action on each row, which is usually the
faster route: start from the record, not the trail.

## Why it cannot be altered

Three independent layers:

1. **The application refuses.** Audit entries cannot be updated or deleted
   through any code path.
2. **The database refuses.** PostgreSQL triggers reject `UPDATE`, `DELETE` and
   `TRUNCATE` on the audit table. Even a direct database session cannot rewrite
   history without first dropping those triggers — itself a visible act.
3. **The chain detects it.** Each entry embeds the hash of the previous one, so
   altering or removing any historic entry invalidates every hash after it.

See [chain integrity](/help/security-and-audit/chain-integrity/).

## It is not surveillance

The trail exists to protect patients and staff, in that order.

If a result is questioned, it shows exactly what was entered, by whom, and what
changed. That defends the person who did the work as often as it identifies a
mistake — "the record shows I entered 5.4 and it was changed afterwards" is only
available if the record exists.

## Exporting

Managers can export the filtered trail as CSV, for an inspector or an
investigation. The export is itself recorded.

## Retention

Audit records are retained for 10 years by default — the period Part 11
implies, since the trail must be available for as long as the records it
describes.

They are never deleted by ordinary operation. The only thing that removes them
is a deliberate [database reset](/help/administration/resetting-the-system/),
which archives them first and records that it happened.
