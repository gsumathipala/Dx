---
title: Exporting results as FHIR and HL7
summary: Sending results to other systems, what each format carries, and what to check.
audience: scientist, manager, administrator
keywords: fhir, hl7, oru, export, diagnosticreport, observation, integration
---

## FHIR

From a report: **FHIR** returns a `DiagnosticReport`; add `?bundle=1` for a
self-contained `Bundle` with the `Patient` and every `Observation`.

| Resource | Carries |
| --- | --- |
| `Patient` | Demographics, MRN as an identifier |
| `Observation` | One result: code, value, units, reference range, interpretation |
| `DiagnosticReport` | The report: status, subject, effective time, its observations, conclusion |

Each `Observation` carries its LOINC code where the test has one, its local code
always, and an interpretation code (`N`, `L`, `H`, `LL`, `HH`) mapped from the
Dx flag.

Status reflects authorisation: `final` once clinically verified, `preliminary`
before.

## HL7 v2

**HL7** returns an `ORU^R01` message as plain text.

```
MSH|^~\&|DX|LAB|||20260915143207||ORU^R01|2026-09-15-0007|P|2.5
PID|1||MRN-100001||Lovelace^Ada||19851210|F
OBR|1|2026-09-15-0007||^Laboratory report|Routine||20260915090000
OBX|1|NM|2345-7^Glucose^LN|1|5.4|mmol/L|3.9-5.8|N|||F|||20260915143000
```

| Segment | Carries |
| --- | --- |
| `MSH` | Message header: sender, timestamp, type, version |
| `PID` | Patient identification |
| `OBR` | The order |
| `OBX` | One result per segment |

`OBX-11` is the result status: `F` for final, `P` for preliminary.

### Escaping

HL7 uses `|`, `^`, `&` and `~` as delimiters, so any of those appearing in data
must be escaped — otherwise a patient named `O'Brien^Smith` would silently break
the segment structure. Dx escapes all four.

## Before connecting to a real system

**Agree the identifiers.** Which identifier is authoritative, and in which
field. Most integration failures are identifier mismatches.

**Agree the codes.** If the receiving system expects LOINC, your catalogue must
be coded to LOINC. Sending local codes means the receiver stores a number it
cannot interpret.

**Agree the units.** And whether the receiver converts or expects yours.

**Test with real edge cases**: a patient with an apostrophe, a name longer than
the field, a result reported as `<0.5`, a cancelled order, an amended result.
Those are where integrations break, and they break in production.

**Decide about amendments.** How does the receiving system show a corrected
result? If it simply overwrites, a clinician may never learn the first answer
was wrong.
