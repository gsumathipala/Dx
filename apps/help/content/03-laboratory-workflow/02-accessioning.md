---
title: "Tutorial: accessioning a request"
summary: Registering a test request, how accession numbers are issued, and what to check before you commit.
audience: clerk, scientist, manager
keywords: tutorial, accessioning, order, request, accession number, barcode
---

## What accessioning is

Accessioning is the point at which a request becomes a tracked piece of work.
It binds three things together: **a patient**, **a set of tests**, and **an
identifier** that follows the sample for the rest of its life.

Everything afterwards depends on getting this right. A test ordered on the
wrong patient produces a perfectly valid result attached to the wrong person.

---

## The tutorial

### Step 1 — Open accessioning

Sidebar → **Accessioning**. Available to clerks, scientists, managers and
administrators.

### Step 2 — Identify the patient

Choose the patient from the list. **Check at least two identifiers** against
the request form — conventionally name and date of birth, or name and MRN.

> Checking two identifiers is standard practice everywhere for the same reason:
> names repeat. In a list of a few thousand patients there will be several
> people called J Smith, and at least one pair sharing a birthday.

If the patient is not registered,
[register them first](/help/patients/registering-patients/).

### Step 3 — Select the tests

Tick every test requested. The list shows code and name; type to filter.

If a request names a profile your laboratory has not configured, ask your
manager rather than approximating.

### Step 4 — Set priority

**Routine** unless the request says otherwise. STAT sorts ahead of everything
and shortens critical value escalation — reserve it.

### Step 5 — Record who requested it

Name the clinician, and select the requester organisation if it is registered.
The requester determines where the report is delivered.

### Step 6 — Specimen type

`Serum`, `Whole blood`, `Urine` and so on. This creates the specimen record and
matters for reception and storage.

### Step 7 — Accession

Press **Accession**. The number appears immediately, in the form
`YYYY-MM-DD-NNNN` — the date, then a sequence within that date.

---

## About accession numbers

**You never type one.** They are issued by the system, in sequence, under a
database lock held until the order is committed. Two people accessioning at the
same instant cannot receive the same number.

> This is a genuinely hard thing to get right, and a common source of bugs.
> Reading "what was the last number?" and then writing a record one step later
> leaves a window where a second request reads the same answer. Holding the
> lock until the write commits closes it.

The suffix is parsed as a number, not compared as text, so the sequence keeps
working beyond 9,999 requests in one day.

### Labelling

Print a label and attach it to the tube **at the point of collection, in the
patient's presence**, not afterwards at a bench. Pre-labelling tubes before
collection, and labelling away from the patient, are the two practices that
most reliably produce misidentified samples.

---

## After accessioning

The order is **Pending** until the specimen is received. It appears on the
receiving screen and in search.

## Common mistakes

| Mistake | Consequence |
| --- | --- |
| Right name, wrong patient (two J Smiths) | Valid result on the wrong record |
| Missing a requested test | Recollection, delay, a complaint |
| Everything marked STAT | Genuine urgency becomes invisible |
| Labelling away from the patient | The commonest route to a swapped sample |

## If you accession in error

Do not delete it. Tell your laboratory manager: an order already accessioned
may have had a specimen taken against it. The audit trail records the creation
either way, and cancelling with a reason is better than a gap.
