---
title: Proficiency testing and external quality assessment
summary: Why comparison with other laboratories catches what internal QC cannot, and the rules around it.
audience: scientist, manager
keywords: proficiency, pt, eqa, external quality, survey, 493.801, attestation
---

## What internal QC cannot see

Internal quality control compares your method against **its own** target values,
established on your own instrument. That detects change over time — drift,
imprecision, a failing component.

It cannot detect that your target values were wrong to begin with. A method
that has been biased since the day it was installed produces beautifully
consistent QC, because the control's assigned mean was derived from the same
biased method.

Only comparison with **other laboratories** reveals that.

## How it works

A provider — CAP, RCPA, UK NEQAS, or a national scheme — sends specimens of
undisclosed value. You analyse them exactly as patient specimens and submit your
results. The provider compares yours with the peer group and grades them.

## The rules that matter

> **CLIA 42 CFR §493.801** requires enrolment in an approved programme for
> regulated analytes, and sets out how specimens must be handled.

**Treat them like patient specimens.** Same staff, same method, same run, same
number of replicates. Testing a PT specimen more carefully than a patient's
tells you how well you *could* perform, which is not the question being asked.

**Do not discuss results with another laboratory before the deadline.** This is
the rule most often broken and taken most seriously. Comparing answers
converts an independent assessment into a consensus, and destroys its value.
In the US it can cost a laboratory its CLIA certificate.

**Do not refer PT specimens to another laboratory.** Even one you routinely
refer patient work to.

Dx will not record a survey as submitted without the attestation that no
inter-laboratory communication took place.

## Recording it

**Settings → Proficiency testing**: provider, survey code, year, event,
discipline, and the dates received, due and submitted. Overdue surveys are
flagged.

**Proficiency results** records each analyte: reported value, target,
acceptable range, z-score and grade.

## Reading a z-score

```
z = (your result − assigned value) / standard deviation of the peer group
```

| z | Interpretation |
| --- | --- |
| Within ±2 | Satisfactory |
| ±2 to ±3 | Questionable — look at it |
| Beyond ±3 | Unsatisfactory — investigate |

A single outlier can be a transcription slip. A **consistent** bias in one
direction across several analytes or several surveys is a calibration problem,
and it has been affecting patients all along.

## When a result is unacceptable

An unacceptable grade is flagged until a corrective action is linked. That is a
requirement, not a convention.

Investigate in this order:

1. **Clerical** — was the right value submitted against the right specimen?
2. **Specimen handling** — was it reconstituted and stored correctly? Lyophilised
   material is unforgiving.
3. **The method** — calibration, reagent lot, instrument condition at the time.
4. **Matrix effects** — some PT material behaves unlike patient specimens on
   some methods. This is a genuine explanation, but it must be demonstrated,
   not assumed.

Then ask the question that matters: **were patient results affected?** If the
method was biased when the survey was analysed, it was biased for patients too.
That may mean reviewing released results and issuing amendments.

## Repeated failure

Persistent unsatisfactory performance in a regulated analyte can lead to a
laboratory being barred from reporting it. That is the intended consequence: a
laboratory that cannot demonstrate agreement with its peers should not be
reporting that test.
