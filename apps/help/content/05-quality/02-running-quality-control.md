---
title: "Tutorial: running quality control"
summary: Entering a control value, reading a Levey-Jennings chart, and what to do when QC fails.
audience: scientist, manager
keywords: tutorial, qc, quality control, westgard, levey-jennings, control, run
---

## What quality control is

You run a specimen of **known** value alongside patient specimens. If the known
value comes back right, the unknown ones probably did too. If it comes back
wrong, they probably did not.

Control material is manufactured to be stable and homogeneous, so a change in
the result reflects the *method*, not the specimen.

---

## Tutorial

### Step 1 — Run the control

Analyse the control material with the patient run, exactly as a patient
specimen: same operator, same reagent lot, same calibration.

Treating a control specially — running it more carefully, at a different time —
defeats the purpose. It must experience whatever the patients experienced.

### Step 2 — Record it

**Quality Control** → select the control and test, enter the measured value,
and record who performed it.

### Step 3 — Read the verdict

The system evaluates it against the Westgard multirules immediately.

| Verdict | Meaning | Do |
| --- | --- | --- |
| **Pass** | Within acceptable limits | Continue |
| **Warning** (1-2s) | Beyond 2 SD, a warning only | Review before reporting |
| **Fail** | A rejection rule violated | Stop; results are blocked |

### Step 4 — If it failed

A failure does three things automatically:

1. **Blocks patient results** for that test from being released.
2. **Opens a nonconformance** with the rule violated and the values.
3. **Flags it** on the compliance dashboard.

You cannot clear it by re-entering. You must find the cause, fix it, and record
an acceptable run.

---

## Reading the Levey-Jennings chart

Each control has a chart: the measured values over time against the target mean
and standard deviations.

```
 +3SD ─────────────────────────────  rejection
 +2SD ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  warning
 +1SD ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
 Mean ━━━━━━━●━━━●━━━━━━━●━━━━━━━━━
 −1SD ─ ─ ─ ─ ─ ─ ─ ─●─ ─ ─ ─ ─ ─ ─
 −2SD ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  warning
 −3SD ─────────────────────────────  rejection
```

The shape matters as much as any single point:

| Pattern | Suggests |
| --- | --- |
| Scatter around the mean | Healthy |
| A sudden **shift** to one side | Reagent lot change, recalibration, new control lot |
| A gradual **trend** | Deterioration: reagent, lamp, electrode, temperature |
| Increasing **scatter** | Imprecision: pipetting, mixing, bubbles |
| One point far out, then normal | Random error — but repeat before dismissing |

A shift and a trend have different causes. A shift usually follows something
you changed; a trend usually follows something that is wearing out.

## Practical notes

**Run at least two levels.** A single mid-range control can look perfect while
the method fails at the top of its range. Two levels bracket the clinically
important region.

**Set the mean from your own data.** Manufacturer inserts give a range for the
material, not your method's performance. Establish your own mean and SD over at
least 20 runs on your instrument, then set the target from that.

**Watch lot changes.** A new control lot has a different target. Run old and new
in parallel to establish the new mean before switching — otherwise a lot change
looks exactly like a method failure.

**Keep the SD honest.** Widening the SD to stop failures is the most common way
a laboratory blinds itself. If QC fails often, fix the method, not the limits.

## What counts as acceptable QC in Dx

Release requires a passing run **within the last 24 hours**. No QC at all is
treated like failed QC: with no evidence the method is working, a result is not
trustworthy.

See [QC lockout](/help/quality/qc-lockout/).
