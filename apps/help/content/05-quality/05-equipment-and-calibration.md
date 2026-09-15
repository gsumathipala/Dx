---
title: Equipment, maintenance and calibration
summary: Instrument records, why calibration expiry blocks use, and what maintenance evidence is for.
audience: scientist, manager
keywords: equipment, instrument, calibration, maintenance, service, analyser, 493.1254
---

## Why instrument records are a regulatory matter

> **CLIA 42 CFR §493.1254** requires instruments to be maintained and
> calibrated according to the manufacturer's instructions, and the records
> retained.

An instrument is the only thing in the chain that can be wrong *consistently*
without anyone noticing. A drifting spectrophotometer does not produce obvious
nonsense; it produces slightly wrong answers for every patient, for as long as
it takes somebody to look.

## The record

**Settings → Equipment**: name, type, serial number, manufacturer, department,
status, and four dates — last and next service, last and next calibration.

| Status | Meaning |
| --- | --- |
| **Active** | In service |
| **Maintenance** | Temporarily out of use |
| **Retired** | Permanently withdrawn |

An instrument past its **calibration date** is flagged and reported on the
compliance dashboard, and is not considered usable for reportable results.

## Calibration versus quality control

These are routinely confused and do different jobs.

**Calibration** establishes the relationship between what the instrument
measures — an absorbance, a current — and the concentration it reports. It uses
material of assigned value, traceable to a reference method or certified
material.

**Quality control** checks that the relationship still holds. It uses material
of known value that is *not* used to set the calibration.

Calibrating against your control material destroys the check: the control will
always agree, because you made it agree. Controls and calibrators must be
independent.

## Maintenance

| Type | Purpose |
| --- | --- |
| **Maintenance** | Scheduled preventive work |
| **Calibration** | Re-establishing the measurement relationship |
| **Repair** | Fixing a fault |
| **Error** | Recording a fault observed |
| **Verification** | Confirming function after work |

Record maintenance as it is done, not at the end of the month. A record written
from memory is evidence of memory, not of maintenance — and an inspector can
tell.

### After any significant work

Repair or recalibration means the instrument is a changed instrument. Before
returning it to patient use:

1. Run quality control at all levels.
2. Where the work could have altered accuracy, verify against known material or
   by comparison with another instrument.
3. Record what was done, by whom, and the outcome.

For a substantial change — a new detector, a new reagent formulation — the
method may need
[revalidation](/help/quality/method-validation/), not merely a QC run.

## Traceability

Results should be traceable to a reference: your calibrator to a certified
reference material, that to a reference method, that to an SI unit where one
exists.

This is what makes a sodium measured in your laboratory comparable with one
measured anywhere else. Where no reference method exists — many immunoassays —
results are method-dependent, which is why a change of platform can shift
values and why that shift must be communicated to clinicians.
