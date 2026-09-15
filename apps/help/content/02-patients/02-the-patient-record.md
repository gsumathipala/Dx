---
title: The patient record and trends
summary: Reading a patient's history, and interpreting a series of results over time.
audience: scientist, medic, manager
keywords: patient, record, history, trend, cumulative, serial
---

## The consolidated record

Opening a patient brings together everything about them: demographics, every
order and its state, critical values raised, consent, disclosures, and the
record's own change history.

Use it when you need context — a clinician queries a result, a delta check
fires, or you are deciding whether an odd value is plausible for this person.

## Trends

**Trends** on a patient shows every numeric result for a chosen test in
chronological order.

### Why a series beats a single value

A single result is compared against a *population* reference interval — the
central 95% of a healthy reference group. That means, by construction, **1 in
20 healthy people fall outside it** for any given test. Run a twelve-analyte
panel on a perfectly healthy person and the chance that everything falls inside
is about 54%.

A patient's own previous results are a far tighter comparator. Biological
variation within one person is usually much smaller than variation between
people. A creatinine of 105 µmol/L is unremarkable against a population
interval of 60–110 — but if this patient has sat at 70 for two years, it is a
50% rise and worth attention.

This is exactly what [delta checks](/help/clinical-decision-support/delta-checks/)
automate, and why the previous value is shown beside each analyte during result
entry.

### Reading a trend

Look for:

- **Direction and rate.** A creatinine rising steadily over months suggests
  something different from one that doubled in two days.
- **Step changes.** An abrupt shift with no clinical explanation may be a
  pre-analytical problem — a different collection site, a change of method, or
  a mislabelled sample.
- **Method changes.** A discontinuity when the laboratory changed analyser or
  reagent lot is a method effect, not a patient effect. This is why method
  validation records matter.

### Serial results and reference change values

Formally, whether a change between two results is real depends on analytical
imprecision and within-subject biological variation combined:

```
RCV = 2^(1/2) × Z × (CVa² + CVi²)^(1/2)
```

where `CVa` is analytical imprecision (from your QC data), `CVi` is
within-subject biological variation (published per analyte), and `Z` is 1.96
for 95% confidence.

For sodium, tightly regulated with `CVi` around 0.6%, even a small change is
significant. For ferritin, with `CVi` around 15%, a result must change
substantially before it means anything. Delta check thresholds should reflect
that difference rather than using one percentage for every test.

## Cumulative reports

**Reports → Cumulative report** builds a grid of one patient's results: tests
down the side, episodes across the top. It is the right format for a ward round
or a clinic letter, where a whole picture matters more than one number.
