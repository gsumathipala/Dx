---
title: Reference intervals
summary: Where a "normal range" comes from, why it depends on age and sex, and how Dx chooses one.
audience: scientist, medic, manager
keywords: reference interval, normal range, reference range, demographic, paediatric, flags
---

## What a reference interval actually is

A reference interval is **the central 95% of results from a defined healthy
reference population**. It is not a boundary between health and disease.

Two consequences follow, and both are routinely forgotten:

**1 in 20 healthy people fall outside it.** By construction. The interval is
defined to exclude 5% of healthy people — 2.5% at each end.

**A panel multiplies that.** If each test is independent, the chance that all
results in a panel fall inside is `0.95ⁿ`:

| Tests in the panel | Chance all are "normal" |
| --- | --- |
| 1 | 95% |
| 5 | 77% |
| 12 | 54% |
| 20 | 36% |

Run a twenty-analyte panel on a healthy person and you are more likely than not
to flag something. This is why a single mildly abnormal result in a large panel
is weak evidence of anything, and why the patient's own previous value matters
more.

## Why they differ by age and sex

Physiology differs. These are not administrative distinctions.

| Analyte | Adult male | Adult female | Why |
| --- | --- | --- | --- |
| Haemoglobin | 130–170 g/L | 120–150 g/L | Androgen-driven erythropoiesis; menstrual loss |
| Creatinine | 60–110 µmol/L | 45–90 µmol/L | Muscle mass |
| Ferritin | 30–400 µg/L | 15–150 µg/L | Iron stores |
| Urate | 200–430 µmol/L | 140–360 µmol/L | Renal handling |

Age matters more still. Alkaline phosphatase in a growing child runs several
times the adult upper limit because bone is actively forming — a child's
"raised ALP" is usually just growth. Neonatal bilirubin, creatinine and
haemoglobin all differ sharply from adult values in the first days of life.

Pregnancy shifts many analytes, and by trimester: plasma volume expands,
diluting haemoglobin and albumin, while alkaline phosphatase rises from the
placenta.

## How Dx chooses an interval

Two layers:

1. **The test's default**, on the test definition, as `min`/`max` with
   `panicLow`/`panicHigh` for critical limits.
2. **Demographic intervals**, which override the default when they apply.

Where several demographic intervals match, the **most specific wins**. Scoring:

| Criterion | Weight |
| --- | --- |
| Age band specified | +2 |
| Sex specified | +2 |
| Pregnancy | +3 |
| Trimester | +2 |

### It will not guess

A demographic interval scoped to an age band is used **only when the age is
known**; one scoped to a sex only when the sex is known. If either is missing,
the interval is skipped and the test default applies.

> This matters. Applying a paediatric interval to a patient of unknown age
> would flag adult results as abnormal, or miss genuinely abnormal paediatric
> ones. A wrong interval is worse than a general one.

## The flags

| Flag | Condition |
| --- | --- |
| **Critical Low** | Below the lower panic limit |
| **Low** | Below the lower reference bound |
| **Normal** | Within, or no applicable bound |
| **High** | Above the upper reference bound |
| **Critical High** | Above the upper panic limit |

**One-sided intervals work.** A test with only an upper bound — cholesterol
below 5.2 mmol/L — flags High above it and Normal below. A test with only a
lower bound behaves symmetrically.

## Verifying an interval before you use it

Adopting a manufacturer's interval is not enough. CLIA 42 CFR §493.1253
requires the laboratory to **verify** that the interval applies to its own
population and method.

The usual minimum is 20 samples from the laboratory's own reference population;
if no more than 2 fall outside the proposed interval, it is accepted.
Populations genuinely differ — by altitude, diet, ethnicity and age structure.

Record it as a [method validation](/help/quality/method-validation/).
