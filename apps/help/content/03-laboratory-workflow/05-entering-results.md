---
title: "Tutorial: entering results"
summary: Recording values, reading the previous result, and what the system does the moment you save.
audience: scientist, medic, manager
keywords: tutorial, results, entry, worklist, keyboard, flags, previous
---

## Finding the work

Sidebar → **Worklist** shows every order not yet complete, ordered by priority
then age. Filter by status, or search by accession number, MRN or surname.

Or scan a tube: the search box takes you straight to that order.

---

## The tutorial

### Step 1 — Open an order

**Open** on any row. The header shows the patient, their age and sex, the
order's state, and how long it has been open.

### Step 2 — Read the table before typing

| Column | What it tells you |
| --- | --- |
| Test | Code and name |
| Result | Where you type |
| Units | The unit expected |
| Reference | The interval for **this** patient's age and sex |
| **Previous** | Their last value, when, and an arrow for direction |
| Flag | How the current value was classified |
| Entered by | Who recorded it |

The **Previous** column is the one to look at. Judging whether a value is
plausible almost always means comparing it with the same patient's last one —
see [trends](/help/patients/the-patient-record/) for why a patient's own
history beats a population interval.

### Step 3 — Type the values

The cursor is already in the first field.

| Key | Does |
| --- | --- |
| `Enter` or `↓` | Next value |
| `↑` | Previous value |
| `Ctrl` + `Enter` | Save |

**Enter moves down; it does not submit.** A twenty-analyte panel should not
need the mouse.

Enter values in the units shown. If your analyser reports different units,
convert before entering — or better, have the interface mapped so it arrives
correctly.

### Step 4 — Add a comment if needed

**Report comment** appears on the report. Use it for anything the clinician
needs to weigh the result: *"Sample slightly haemolysed; potassium may be
falsely elevated."*

A result with a known limitation and no comment is worse than no result.

### Step 5 — Save

**Save results.** Several things happen at once:

- Each value is compared against the interval for this patient and flagged.
- **Delta checks** compare each with the patient's previous value.
- **Critical values** raise a notification if outside the panic limits.
- **Reflex rules** may add a follow-on test.
- **Notifiable conditions** raise a public health notification.
- **Reagent stock** is decremented.

Anything raised appears as a message at the top of the screen. Read them —
a critical value needs a telephone call, not just a saved form.

---

## Non-numeric results

Qualitative results — `Not detected`, `Positive`, `Growth`, `See comment` —
are entered as text. They are not flagged against a numeric interval, and delta
checks do not apply.

## Correcting a value before release

Simply re-enter it and save. The old value is kept in the audit trail with your
name against the change.

Once the report is **released**, correcting it requires an
[amended report](/help/reporting/amended-reports/) — a different and more
serious process, because a clinician has already seen the first answer.

## What you cannot do here

| Refused | Why |
| --- | --- |
| Verify a result you entered | A second person must review it |
| Release while QC is failing | The measurement is not trustworthy |
| Validate a test you are not competent in | CLIA requires assessed competency |

These are controls, not faults. See
[When the system stops you](/help/troubleshooting/when-the-system-stops-you/).
