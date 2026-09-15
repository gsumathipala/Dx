---
title: Method validation and verification
summary: Proving a method performs as claimed before patient results depend on it.
audience: scientist, manager
keywords: validation, verification, accuracy, precision, reportable range, 493.1253, ldt
---

## Verification versus establishment

**Verification** applies to an unmodified FDA-cleared or CE-marked method used
as the manufacturer intends. You confirm it performs *in your hands* as claimed.

**Establishment** applies to a laboratory-developed test, or any modified
method. You must determine the performance characteristics yourself, from
scratch. It is a much larger undertaking.

> **CLIA 42 CFR §493.1253(b)(1)** requires verification of accuracy, precision,
> reportable range and reference intervals before reporting patient results with
> any non-waived test.

## The four elements

Dx will not let a validation be marked **Approved** until all four are recorded
as verified, and names whichever are outstanding.

### Accuracy

Does it give the right answer? Assessed by comparison with a reference method,
certified reference material, or a peer laboratory, across the clinical range.

Analyse a set of specimens by both methods and compare — conventionally by
Deming or Passing-Bablok regression, which (unlike ordinary least squares)
allow for error in both methods. Look at the slope for proportional bias and
the intercept for constant bias.

### Precision

Does it give the **same** answer on repetition?

- **Within-run** (repeatability): replicates in one run.
- **Between-run** (intermediate precision): over days, operators, calibrations.

Usually at least 20 runs at two or three concentrations. Between-run precision
is what matters clinically — a patient's results are compared across days, not
within a single run.

Precision is the input to the reference change value that sets sensible
[delta check](/help/clinical-decision-support/delta-checks/) thresholds.

### Reportable range

Over what span is the method linear and trustworthy? Determined with a dilution
series across the claimed range.

This defines what you may report numerically, and where results must be
reported as "greater than" or "less than" — and where a specimen must be
diluted and re-run.

### Reference interval

Does the manufacturer's interval apply to **your** population? See
[reference intervals](/help/clinical-decision-support/reference-intervals/).
The usual minimum for verification is 20 specimens from your own reference
population, accepting the interval if no more than 2 fall outside.

## Also worth recording

**Analytical sensitivity** — the limit of detection and limit of quantitation.
The lowest concentration reliably distinguished from zero, and the lowest
reported as a number.

**Analytical specificity** — what interferes. Haemolysis, lipaemia, icterus,
common drugs, cross-reacting substances.

## When to revalidate

- A new instrument, or a relocated one
- A change of method or manufacturer
- A significant reagent reformulation
- After major repair affecting the measurement
- Persistent proficiency testing failure
- A change to the reference interval

Record it as a **Revalidation** so the history of the method is visible.

## Recording it

**Settings → Method validation**: the test, kind, instrument, who performed it,
dates, the four elements, sensitivity and specificity, a summary, and the
approval.

Approval should be by someone qualified to judge it — typically the laboratory
director or technical supervisor. Signing it off records that a competent person
considered the evidence sufficient.
