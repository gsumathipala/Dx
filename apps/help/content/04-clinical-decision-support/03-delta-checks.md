---
title: Delta checks
summary: Comparing a result with the patient's own previous value, what it catches, and how to set thresholds.
audience: scientist, manager
keywords: delta check, previous, change, sample swap, threshold, biological variation
---

## The idea

A delta check compares a result with the same patient's **previous result for
the same test**, and flags a change larger than expected.

It is the single most effective automated check for one specific failure:
**the sample that belongs to somebody else**. A swapped sample produces a
perfectly normal-looking result that is simply the wrong person's. Nothing about
the value itself gives it away — but compared with the patient's own history it
often looks impossible.

## What it catches

| Cause | Typical appearance |
| --- | --- |
| Sample misidentification | Everything shifts at once, plausibly, in no clinical pattern |
| Contaminated draw (drip line) | Glucose or sodium implausibly high, others diluted |
| Genuine clinical change | One or two related analytes move together |
| Analytical error | One analyte shifts, others do not |
| Method or lot change | Step change across many patients at once |

The last is worth noting: if delta checks fire on several patients the same
morning, suspect the **method**, not the patients.

## Setting thresholds

A rule specifies test, threshold, type and direction.

| Setting | Meaning |
| --- | --- |
| **Percent** | Relative change — for analytes whose normal value varies widely |
| **Absolute** | Change in the unit of measurement — for tightly regulated analytes |
| **Direction** | Any, increase only, or decrease only |
| **Lookback** | How far back to search for a comparable result |

### One percentage does not fit every test

How much a result *can* vary within one healthy person differs enormously by
analyte. This is *within-subject biological variation* (`CVi`):

| Analyte | Approx. `CVi` | Sensible delta approach |
| --- | --- | --- |
| Sodium | 0.6% | Small absolute change is significant |
| Calcium | 2% | Small absolute change |
| Creatinine | 6% | Modest percentage |
| ALT | 20% | Large percentage before it means anything |
| Ferritin | 15% | Large percentage |
| Triglycerides | 20%+ | Large percentage |

A 20% change in sodium would be catastrophic; a 20% change in ferritin is
ordinary. Using one threshold everywhere produces alarms nobody reads.

Formally, the *reference change value* combines analytical and biological
variation:

```
RCV = 2^(1/2) × 1.96 × (CVa² + CVi²)^(1/2)
```

`CVa` comes from your own QC data. Setting thresholds near the RCV means a flag
represents a change unlikely to be chance.

### Direction

Direction matters clinically. A falling haemoglobin suggests bleeding; a rising
one rarely needs urgent attention. A decrease-only rule halves the alerts
without losing what you care about.

> An **unchanged** value is neither an increase nor a decrease, so a
> direction-specific rule does not fire on identical results.

### Lookback

Default 30 days. Long enough to find a comparator, short enough that the
comparison is meaningful — comparing today's result with one from two years ago
says little.

## What Dx compares against

The most recent numeric result for the same patient and test that is
**genuinely earlier** than the order being resulted, within the lookback
window.

> Comparing against a *later* result is a real hazard when results are entered
> out of order — a batch resulted this afternoon may include yesterday's
> collections. Dx compares only against earlier ones.

## Responding to a flag

A delta flag is a prompt to think, not a reason to withhold.

1. **Is it clinically explicable?** A transfused patient's haemoglobin should
   rise. A patient started on diuretics should shift potassium.
2. **Does the whole panel move together?** One analyte moving is usually
   biology. Everything moving plausibly but differently suggests the wrong
   patient.
3. **Check the specimen.** Right patient, right tube, plausible collection time.
4. **Repeat if unsure.** A repeat on the same specimen tests the measurement; a
   fresh specimen tests the whole chain.

If you conclude the sample was misidentified, that is a nonconformance — raise
it, because it almost never affects only one sample.
