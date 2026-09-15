---
title: Calculated tests
summary: Analytes derived from other results — the formulae, their units, and when each stops being valid.
audience: scientist, medic, manager
keywords: calculated, derived, egfr, ldl, anion gap, formula, friedewald, ckd-epi
---

## What a calculated test is

An analyte computed from other measured results rather than measured directly.
It costs nothing extra, arrives instantly — and is only as good as its inputs
and its assumptions.

Every formula below has conditions under which it stops being valid. Knowing
those conditions is the difference between a useful derived value and a
misleading one.

## The formulae

### LDL cholesterol — Friedewald

```
LDL = Total cholesterol − HDL − (Triglycerides / 2.2)     [mmol/L]
```

The `/2.2` estimates VLDL cholesterol from triglycerides, assuming a fixed
ratio in VLDL particles.

> **Invalid when triglycerides exceed 4.5 mmol/L**, because the assumed ratio
> breaks down. Dx returns no result rather than a wrong one. It is also
> unreliable in non-fasting samples and in type III hyperlipoproteinaemia.

### eGFR — CKD-EPI 2021

```
eGFR = 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^−1.200 × 0.9938^age × 1.012 [if female]
```

with `Scr` in mg/dL, `κ` = 0.7 (female) or 0.9 (male), `α` = −0.241 (female) or
−0.302 (male). Dx converts from µmol/L by dividing by 88.4.

The **2021** equation deliberately omits the race coefficient present in
earlier versions. That coefficient raised estimated GFR for Black patients,
which delayed referral and transplant listing; the revision removed it.

> Requires age and sex. Unreliable in acute kidney injury — the equation
> assumes steady state, and in AKI creatinine lags the true GFR by many hours,
> so eGFR overestimates function exactly when it matters. Also unreliable at
> extremes of muscle mass.

### Anion gap

```
Anion gap = Na⁺ − (Cl⁻ + HCO₃⁻)                            [mmol/L]
```

Reference roughly 8–16 mmol/L. It quantifies unmeasured anions and separates
causes of metabolic acidosis: a **raised** gap suggests ketoacidosis, lactic
acidosis, renal failure or certain poisonings; a **normal** gap suggests
bicarbonate loss, such as diarrhoea or renal tubular acidosis.

> Falsely low in hypoalbuminaemia — albumin is the main unmeasured anion. Some
> laboratories correct by adding 2.5 mmol/L per 10 g/L of albumin below 40.

### Albumin-corrected calcium

```
Corrected Ca = Measured Ca + 0.02 × (40 − albumin)         [mmol/L, albumin g/L]
```

Roughly half of circulating calcium is albumin-bound and physiologically
inactive. A low albumin lowers total calcium without affecting ionised calcium,
so an uncorrected total misleads.

> An approximation, and unreliable in critical illness and pregnancy. Where the
> answer matters, measure ionised calcium directly.

### Albumin/globulin ratio

```
A:G = Albumin / (Total protein − Albumin)
```

Returns nothing if globulin computes to zero or below — which indicates an
error in one of the inputs, not a real value.

### Calculated osmolality

```
Osmolality = 2 × Na⁺ + urea + glucose                      [mmol/L]
```

Compared with a measured osmolality to give the **osmolar gap**. A large gap
suggests an unmeasured osmotically active substance — ethanol, methanol,
ethylene glycol — and can be the first clue in a poisoning.

### Transferrin saturation

```
Saturation = (Iron / TIBC) × 100                           [%]
```

Reference roughly 20–50%. Low suggests iron deficiency; high suggests iron
overload or haemochromatosis.

## Configuring one

**Settings → Calculated tests**: a code, a name, the formula, its required
input test codes and a unit.

The inputs must be present and numeric on the same order. A calculated test
returns nothing when an input is missing — rather than substituting a default,
which would produce a confident wrong answer.

## How to treat them on a report

A calculated value should be recognisable as calculated. It carries the
assumptions of its formula, and a clinician needs to know that an eGFR in acute
illness, or an LDL at high triglycerides, is not to be relied on.
