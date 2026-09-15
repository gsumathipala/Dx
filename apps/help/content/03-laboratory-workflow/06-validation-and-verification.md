---
title: Validating and verifying results
summary: The two authorisation stages, the checks behind each, and the signature you apply.
audience: scientist, medic, manager
keywords: validation, verification, authorise, release, signature, two-stage, clia
---

## Two questions, not one

**Technical validation** — *is this measurement sound?*
Quality control acceptable, instrument behaving, values internally consistent,
no evidence of a pre-analytical problem. A question about the **process**.

**Clinical verification** — *should this be reported?*
Plausible for this patient, consistent with their history, comment needed,
someone to telephone. A question about the **patient**.

Different questions, often different people. Collapsing them loses the second
look — which is the entire purpose.

## Doing it

Open the order. The screen offers **only the action it is ready for**: one
button, not three where two would be refused.

Enter your password and confirm. Clinical verification completes the order and
releases the report.

## Why your password, every time

Your password is your **electronic signature**. 21 CFR Part 11 §11.200(a)(1)
requires that a signature applied by someone already signed in uses at least
one component — here, the password — *at the moment of signing*.

Being signed in proves you were there earlier. It does not prove you are the
one clicking now. Someone who walked away from an unlocked workstation has not
signed anything.

The signature records your printed name, your role, the exact time, the meaning
of the signature, and a hash of the content signed — so it cannot be detached
and reapplied to a different result.

## The three gates

### Competency

You must hold a current competency record for the test, or for its discipline.

> **CLIA 42 CFR §493.1451(b)(8)** requires competency assessment before staff
> report patient results — semi-annually in the first year, annually
> thereafter. An expired record stops satisfying the gate on its expiry date,
> not when someone remembers to update it.

### Quality control

The most recent QC for the test must have passed, and there must have been QC
within 24 hours.

> **CLIA 42 CFR §493.1256** requires acceptable QC before patient results are
> reported. A failing QC blocks release until it is investigated and repeated —
> see [QC lockout](/help/quality/qc-lockout/).

### Self-verification

The person who entered a result cannot verify it. If you entered it, the screen
tells you a second qualified person is needed.

## Verifying several orders at once

On the **Worklist**, orders ready for clinical verification carry a checkbox.
Tick several, enter your password once, and choose **Verify selected**.

One signing covers the batch, and the signature records exactly which orders it
covered — which is what Part 11 §11.50 requires of a signature manifest.

**Each order is still checked individually.** If one fails a gate you are told
which and why, and the others still go through.

## Auto-verification

Dx does **not** auto-verify results. Every release is authorised by a named
person.

Auto-verification is legitimate and widely used, but it must respect QC status,
competency and reference intervals, and must never release a critical value or
a delta-flagged result unseen. Implemented carelessly it becomes a hole through
every control above.
