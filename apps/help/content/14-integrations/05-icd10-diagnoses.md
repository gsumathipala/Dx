---
title: ICD-10 diagnosis codes
summary: Why a laboratory records the clinical indication, and what the system does with it.
audience: manager, clerk, medic
keywords: ICD-10, diagnosis, indication, medical necessity, DG1, coding
---

## Three different reasons

A laboratory records diagnosis codes for three reasons that pull in different
directions. It is worth being clear which one you are serving.

### Clinical context

A sodium of 128 means something different on a patient coded **E87.1**
(hyponatraemia, already known and being managed) than on one coded **R55**
(syncope, being worked up). The [decision
rules](/help/rules-and-automation/writing-a-rule/) can condition on the code, so
an interpretive comment can say something useful rather than something generic.

### Medical necessity

Payers in several jurisdictions reimburse a test only when the indication
justifies it. The code travels with the order, so a claim can be built without
a second round trip to the requester.

### Epidemiology and audit

Coded indications are what make *"how many D-dimers did we run for suspected PE
last quarter, and what proportion were positive?"* a query rather than a
project.

## Where codes come from

| Route | How |
| --- | --- |
| Inbound HL7 orders | `DG1` segments, or `OBR-31` if there are none |
| The API | A `diagnoses` array when placing an order |
| The catalogue | **Settings → ICD-10 codes**, maintained by the laboratory |

A code that arrives on an order but is not in the local catalogue is **still
recorded**. The hospital's coding is the record, even when your lookup table
lags it.

## What is stored

Each diagnosis on an order keeps the **code and its description as they were at
the time**, not just a link to the catalogue row.

That is deliberate. ICD-10 is revised; codes are withdrawn and their wording
changes. A diagnosis recorded against a specimen in 2026 must still read
correctly in 2031, after the catalogue entry has been superseded. The link is
for lookup; the copy is the record.

Diagnoses are **ranked** — rank 1 is the primary indication, which is the one a
payer reads.

## What this is not

Dx does **not** hold an ICD-10 licence and is not a terminology server. The
table is a lookup the laboratory populates from whatever authoritative source
it is entitled to use. There is no hierarchy, no inclusion and exclusion notes,
no national modification handling, and no mapping to SNOMED CT.

If you need those, you need a terminology server, and the right integration is
for that server to be authoritative and Dx to hold the codes it is told.

## Loading the catalogue

**Settings → ICD-10 codes → New** for a handful. For a full set, ask your
administrator — the `Icd10Code` model takes a bulk load, and the API exposes
`GET /api/v1/icd10/?q=` for lookups from a front end.

Untick **billable** on category headings that are not themselves codeable to a
claim, so nobody attaches one to an order by accident.
