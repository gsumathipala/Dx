---
title: How the workflow fits together
summary: The stages an order passes through, what each guarantees, and why authorisation happens twice.
audience: everyone
keywords: workflow, states, lifecycle, order, status, overview
---

## The path of an order

```
  Accessioning  →  Receiving  →  Result entry  →  Technical    →  Clinical     →  Released
                                                   validation      verification
   identity        condition      measurement      run is          result is       clinician
   established     assessed       recorded         sound           reportable      can act
```

Each stage exists because something can go wrong there, and each leaves a
record of who was satisfied that it had not.

## The states

| State | Meaning | Next |
| --- | --- | --- |
| **Pending** | Accessioned, specimen not yet received | Receiving |
| **Received** | Specimen arrived and accepted | Result entry |
| **Resulted** | Values entered, not yet authorised | Technical validation |
| **Technically Validated** | Analytical run accepted | Clinical verification |
| **Completed** | Verified and released | — |
| **Rejected** | Specimen unsuitable; recollection needed | — |

The worklist shows everything not yet complete. The dashboard groups it by
which stage it is waiting at, so you can see where work is piling up.

## Why authorisation happens twice

This is the part newcomers most often question, so it is worth spelling out.

**Technical validation** asks: *is this measurement sound?* Was quality control
acceptable, did the instrument behave, are the values internally consistent, is
there evidence of a pre-analytical problem such as haemolysis? This is a
question about the **process**.

**Clinical verification** asks: *should this result be reported to a
clinician?* Is it plausible for this patient, does it fit their history, does
it need a comment, does someone need telephoning now? This is a question about
the **patient**.

They are different questions, often answered by different people with different
training. Collapsing them into one click loses the distinction and, with it,
the second look.

> **CLIA 42 CFR §493.1495** requires review of results by a qualified person
> before release. Dx enforces the related rule that **the analyst who produced
> a result cannot be the one who verifies it** — a second pair of eyes is not
> a second click by the same eyes.

## What is checked before release

Before technical validation or clinical verification succeeds, three gates run:

| Gate | Asks | If it fails |
| --- | --- | --- |
| **Competency** | Are you currently assessed as competent for this test? | Refused, with the test named |
| **QC status** | Was quality control acceptable in the last 24 hours? | Refused; results stay blocked |
| **Self-verification** | Did you enter this result yourself? | Refused for verification |

Plus the electronic signature: your password, every time.

None of these can be worked around from inside the application. They are the
controls, not obstacles in front of them.

## Priority

| Priority | Meaning |
| --- | --- |
| **Routine** | Ordinary turnaround |
| **Urgent** | Expedited |
| **STAT** | Immediate — sorts first everywhere, escalates critical values in 30 minutes rather than 60 |

Use STAT sparingly. A laboratory where everything is STAT has no way to
identify what genuinely is.

## Turnaround time

TAT is measured from order to completion and compared against thresholds set
per test, per department, or globally, with warning and breach levels.

**Turnaround** shows every open order against its target. It is the single best
indicator of whether the laboratory is coping, and the clinical complaint that
most often reaches the laboratory director.
