---
title: The Westgard multirules explained
summary: Each rule, what it detects, and why one rule alone is not enough.
audience: scientist, manager
keywords: westgard, rules, 1-3s, 2-2s, r-4s, 4-1s, 10x, random error, systematic error
---

## Why several rules

A single limit forces a bad trade. Set it at 2 SD and you reject roughly 5% of
perfectly good runs — with two control levels, nearly 10%, which is a false
alarm most days. Set it at 3 SD and you miss real problems.

Westgard's insight was to use **several rules together**: one very specific rule
to catch large random errors, and several pattern rules to catch systematic
errors that no single point would trigger.

The two error types need different detection:

**Random error** — scatter. One point far from the mean. Caught by a
single-point rule.

**Systematic error** — bias. Every point shifted slightly. Each individual point
may sit within limits, so only a *pattern* reveals it.

## The rules

### 1-2s — warning

One control beyond 2 SD.

Not a rejection. In a healthy method roughly 1 result in 20 lands here by
chance. Treated as rejection it would produce constant false alarms; its proper
use is as a trigger to look at the other rules.

### 1-3s — rejection

One control beyond 3 SD.

Detects large **random error**. About 1 in 370 by chance, so a violation
usually means something real: a bubble, a short sample, a mis-pipetted control,
a transient instrument fault.

### 2-2s — rejection

Two consecutive controls beyond the **same** 2 SD limit.

Detects **systematic error**. Two points both beyond +2 SD is far less likely by
chance than two scattered points, and indicates the method has shifted rather
than wobbled.

### R-4s — rejection

Two consecutive controls differing by more than 4 SD — one above +2 SD and one
below −2 SD.

Detects **imprecision** specifically. The mean may be fine, but the spread has
widened: air bubbles, inadequate mixing, a failing pipette, temperature
instability.

### 4-1s — rejection

Four consecutive controls beyond the **same** 1 SD limit.

Detects a **small systematic shift**. Individually unremarkable, but four in a
row on the same side is a bias — often a new reagent lot or a drifting
calibration.

### 10x — rejection

Ten consecutive controls on the **same side** of the mean, regardless of
distance.

Detects a **very small persistent bias**. Ten coin tosses landing the same way
is about 1 in 500 — the method has moved, even if no point looks abnormal.

## Summary

| Rule | Detects | Typical cause |
| --- | --- | --- |
| 1-2s | Warning only | Chance |
| 1-3s | Large random error | Bubble, short sample, transient fault |
| 2-2s | Systematic shift | Calibration, reagent lot |
| R-4s | Imprecision | Mixing, pipetting, temperature |
| 4-1s | Small systematic shift | Reagent lot, drifting calibration |
| 10x | Small persistent bias | Slow drift, wrong target value |

## How Dx applies them

Every recorded run is evaluated against all six, using the preceding runs for
the same control as history. The verdict is:

- **Fail** if any rejection rule is violated (1-3s, 2-2s, R-4s, 4-1s, 10x)
- **Warning** if only 1-2s
- **Pass** otherwise

A failure blocks patient results and opens a nonconformance automatically.

## Choosing which rules to apply

Westgard's own guidance is that the rule set should match the method's
capability. A method with wide analytical performance relative to its
requirement can use 1-3s alone and reject almost nothing falsely. A method
operating close to its limit needs the full set to catch errors that matter.

Dx applies the full set. Where that produces frequent failures on a stable
method, the usual cause is a target SD set too tightly — from too few
observations, or from a different reagent lot.
