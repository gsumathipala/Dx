---
title: QC lockout
summary: Why failing QC blocks patient results, what to do about it, and why it cannot be overridden.
audience: scientist, manager
keywords: qc lockout, blocked, failed, release, clia, 493.1256
---

## What lockout does

When the most recent quality control for a test has **failed**, or when there
has been **no QC in the last 24 hours**, patient results for that test cannot be
technically validated or clinically verified.

The result can still be entered. It cannot be released.

## Why

> **CLIA 42 CFR §493.1256(d)** requires the laboratory to establish that its
> control procedures are acceptable **before** reporting patient results, and
> §493.1256(d)(3) requires that a failed run be investigated and corrective
> action documented.

The logic is direct. QC is the only evidence the method worked. If that evidence
says it did not, there is no basis for believing any patient result from the
same run. Releasing anyway means reporting results you have positive evidence
are unreliable.

**No QC at all is treated the same as failed QC.** Absence of evidence is not
evidence the method worked.

## What to do

1. **Do not repeat the control hoping for a pass.** A control that passes on the
   second attempt with nothing changed tells you the method is unstable, which
   is itself the finding.
2. **Look at the chart.** A shift, a trend and a single outlier point to
   different causes — see [running quality control](/help/quality/running-quality-control/).
3. **Check the obvious**: reagent expiry and lot, calibration date, control
   expiry and storage, instrument maintenance due, an error log.
4. **Fix the cause.**
5. **Run fresh control material** and record it. An acceptable run clears the
   block.
6. **Complete the nonconformance** that was opened automatically — root cause,
   corrective action, and whether patient results were affected.

## Results already released

If patient results were released before the failure was detected, they may be
affected. Decide how far back the problem extends — usually to the last known
acceptable QC — and review results in that window.

Where a released result was wrong, issue an
[amended report](/help/reporting/amended-reports/) and tell the requesting
clinician. That is the part that actually protects the patient.

## Why it cannot be overridden in the interface

There is deliberately no button to release against failed QC.

An override available under pressure will be used under pressure, which is
exactly when judgement is worst. If a laboratory genuinely must operate without
it — during commissioning, say — `ENFORCE_QC_LOCKOUT` can be turned off in
configuration, which is a visible, deliberate act shown on the compliance
dashboard, not a click in a moment of haste.

## Emergencies

If a result is needed urgently and QC is failing, the answer is not to release
it silently. Speak to the laboratory director. The options are to repeat on a
verified method, send to a referral laboratory, or release with an explicit
documented caveat under the director's authority — all of which leave a record.
