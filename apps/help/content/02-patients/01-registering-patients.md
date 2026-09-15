---
title: Registering patients
summary: Creating and correcting a patient record, and why identity is the foundation of everything else.
audience: clerk, scientist, manager, administrator
keywords: patient, mrn, demographics, registration, identity, duplicate
---

## Why identity comes first

Every safeguard downstream — reference intervals, delta checks, critical value
notification, the report itself — assumes the sample belongs to the person the
record names. If that assumption fails, every later control fails with it,
usually silently.

Misidentification is consistently among the most serious laboratory errors
because it produces a *plausible* wrong answer. An analyser fault produces
nonsense somebody notices. A swapped sample produces a normal-looking result
for entirely the wrong person.

## Registering a patient

**Patients → New patient.**

| Field | Notes |
| --- | --- |
| First name, surname | As they appear on the identification used |
| Date of birth | Drives age-specific reference intervals and eGFR |
| Sex | Drives sex-specific reference intervals |
| **MRN** | The unique identifier. Must not already exist. |
| Email, phone, address | Optional; used for report delivery |

### The medical record number

The MRN is how this patient is recognised everywhere — in search, on reports,
in the audit trail. It must be unique, and the system refuses a duplicate.

If your laboratory receives work from several hospitals, agree an MRN
convention before you start. Two hospitals each using `12345` for different
patients is a merge problem that gets harder every day you leave it.

### Why sex and date of birth are not optional

They are not demographics-for-the-sake-of-it. Reference intervals differ
materially:

| Analyte | Adult male | Adult female |
| --- | --- | --- |
| Haemoglobin | 130–170 g/L | 120–150 g/L |
| Creatinine | 60–110 µmol/L | 45–90 µmol/L |
| Ferritin | 30–400 µg/L | 15–150 µg/L |

And by age, more dramatically still — a neonatal creatinine reflects the
mother's for the first days of life, and alkaline phosphatase in a growing
child is several times the adult upper limit.

A result judged against the wrong interval is flagged wrongly, and a wrongly
flagged result is either a false alarm or a missed diagnosis.

**Dx will not apply an age- or sex-specific interval when it does not know the
age or sex.** It falls back to the test's default rather than guessing.

## Correcting a record

Managers and administrators can edit a patient. Every change records the old
and new value against your account.

Correct demographics as soon as you find an error: a wrong date of birth is
silently changing how every result for that patient is interpreted.

## Duplicates

If you find the same person registered twice, do not simply delete one — the
orders attached to it would lose their patient. Raise it with your laboratory
manager, who can decide which record survives and arrange for the other's work
to be moved.

Prevention is easier: search before registering. Try the surname alone; people
are registered under married and maiden names, with and without hyphens, and
with initials in place of first names.

## What the record shows

Open a patient to see demographics and age, every order with its status,
critical values raised, consent records, disclosures of their information, and
recent changes to the record.

**Opening a patient record is itself recorded** as a disclosure of protected
health information — see [Privacy and consent](/help/patients/privacy-and-consent/).
