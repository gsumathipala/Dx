---
title: "Tutorial: your first hour"
summary: A guided walk through the whole workflow, from registering a patient to a released report.
audience: everyone
keywords: tutorial, walkthrough, first, getting started, workflow
---

## Before you start

You will need an account that can accession and enter results — a
**scientist**, **manager** or **administrator**. If you are working on a
demonstration system, sign in as `bscientist`.

This takes about twenty minutes and walks the entire workflow. Nothing here
affects real patients if you use a demonstration database.

---

## Step 1 — Register a patient

1. Sidebar → **Search**, then **Patients** from the settings index (or go to
   `/patients/`).
2. **New patient**.
3. Enter a first name, surname, date of birth, sex and a medical record number.
   The MRN must be unique — it is how this patient is recognised everywhere
   else.
4. **Save**.

**What just happened:** the patient exists, and an audit entry records that you
created them, with every field's initial value.

> A future date of birth is refused. Small guards like this stop a typo
> becoming a patient who has not been born.

---

## Step 2 — Accession a request

1. Sidebar → **Accessioning**.
2. Choose your patient.
3. Tick two or three tests.
4. Set priority to **Routine**, name a requesting clinician, and set the
   specimen type to `Serum`.
5. **Accession**.

**What just happened:** the system allocated an accession number of the form
`YYYY-MM-DD-NNNN`. You never type one — numbers are issued under a lock so two
people accessioning simultaneously cannot receive the same number.

Note it down; you will search for it shortly.

---

## Step 3 — Find it by searching

1. Click the search box at the top of the sidebar (or press `/`).
2. Type the accession number and press Enter.

**What just happened:** you were taken straight to the order at its current
stage. If a barcode label had been printed, scanning it would have done exactly
the same thing.

---

## Step 4 — Receive the specimen

1. Sidebar → **Receiving**.
2. Choose the specimen and order.
3. Set condition **Acceptable**, status **Accepted**.
4. **Record receipt**.

**What just happened:** the order moved to *Received*. Had you marked it
rejected, the system would have required a rejection reason — the requester
must be told what to recollect and why.

---

## Step 5 — Enter results

1. Sidebar → **Worklist**. Your order is listed.
2. **Open**.
3. The cursor is already in the first value. Type a number and press **Enter** —
   it moves down. Fill in the panel without touching the mouse.
4. **Save results**.

**What just happened — several things at once:**

- Each value was compared against its reference interval and flagged
  High/Low/Critical as appropriate.
- Delta checks compared each against the patient's previous value.
- Any critical value raised a notification.
- Reflex rules may have added a follow-on test.
- Reagent stock was decremented.

Look at the **Previous** column: for a patient with earlier results it shows
the last value and an arrow. That comparison is usually the whole judgement.

---

## Step 6 — Technically validate

Still on the order:

1. The screen now offers **Technically validate** — and only that. It shows the
   action the order is ready for, not every action that exists.
2. Enter your password.
3. **Technically validate**.

**What just happened:** you asserted the analytical run was sound, and applied
an electronic signature. Your password was required because a signature must
prove it was *you* at that moment.

Two checks ran first: your competency for these tests, and whether quality
control is currently acceptable. Either would have refused you.

---

## Step 7 — Clinically verify (as someone else)

1. **Sign out**, and sign back in as a different person — try `lmanager`.
2. Search the accession number again.
3. The screen now offers **Clinically verify and release**.
4. Enter that user's password and confirm.

**What just happened:** the order completed and the report was released.

Try it as the *same* person who entered the results and you will be refused:
**the analyst who produced a result cannot be the one who verifies it.** A
second pair of eyes is the point.

---

## Step 8 — Read the report

1. Sidebar → **Reports**, find your accession number, **Open**.
2. The report shows demographics, results with units, reference intervals,
   flags, any comment, and the **signature manifest** — who authorised it, when,
   and in what capacity.
3. **Print** lays it out for paper. **FHIR** and **HL7** export it for another
   system.

---

## Step 9 — See what you did

1. Sidebar → **Audit Trail**.
2. Your work from the last twenty minutes is at the top.
3. Open any entry: the field-level before and after, your username, the time,
   your address, and the entry's position in the hash chain.
4. From an entry, follow **Record history** to see everything that ever
   happened to that record.

**What just happened:** nothing special — this is recorded for every change, by
everyone, permanently. It cannot be edited or deleted by anyone, including
administrators.

---

## What to explore next

| Try | Where |
| --- | --- |
| Make QC fail and watch results get blocked | [Running quality control](/help/quality/running-quality-control/) |
| Document a critical value read-back | [Critical values](/help/clinical-decision-support/critical-values/) |
| Correct a released report | [Amended reports](/help/reporting/amended-reports/) |
| Verify the audit chain | [Chain integrity](/help/security-and-audit/chain-integrity/) |
