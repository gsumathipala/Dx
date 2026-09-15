---
title: Patient reports
summary: What a report contains, why each element is there, and how to read the signature block.
audience: everyone
keywords: report, print, signature, manifest, release
---

## What a report is

A report is the laboratory's formal answer, and in most jurisdictions a legal
record. It is the thing a clinician acts on and the thing examined if that
action is later questioned.

**Reports** lists every released report. Open one to view, print, or export it.

## What it contains, and why

| Element | Why it is there |
| --- | --- |
| Patient name, MRN, date of birth, sex | Identity — checked against the request |
| Accession number | Links the report to the specimen |
| Requesting clinician | Who asked, and who to tell |
| Collection time | When the snapshot was taken |
| Report time | When the answer became available |
| Each result with units | The answer, unambiguously |
| Reference interval | What "normal" means here |
| Flags | High, Low, Critical |
| Comment | Anything that qualifies the result |
| **Signature manifest** | Who authorised it, when, in what capacity |

### Units are not decoration

The same analyte reported in different units differs by orders of magnitude.
Glucose is 5.5 mmol/L or 99 mg/dL; creatinine is 88 µmol/L or 1.0 mg/dL. A
number without its unit is not a result, and a clinician reading a report from
an unfamiliar laboratory relies on the unit being present.

### The reference interval belongs next to the result

Reference intervals are method- and population-dependent. A result of 4.2 means
nothing without knowing whether this laboratory's interval is 3.5–5.0 or
4.0–6.0. Printing them together is what makes the report interpretable
elsewhere.

## The signature manifest

At the foot of every report:

```
Clinically approved by: Senior Biomedical Scientist (manager)
  — 2026-09-15 14:32:07 UTC · identity re-verified at signing
```

21 CFR Part 11 §11.50 requires a signed record to display the signer's printed
name, the date and time, and the **meaning** of the signature. "Approved by" and
"reviewed by" are different assertions, and the manifest says which.

"Identity re-verified at signing" records that a password was entered at the
moment of signing, not merely at login.

## Printing

**Print** lays the report out for paper — sidebar, buttons and navigation are
omitted. Use the browser's print dialogue for paper size and margins.

## Exporting

| Format | Use |
| --- | --- |
| **FHIR** | Modern EHR integration; `?bundle=1` for a self-contained bundle |
| **HL7** | HL7 v2 ORU^R01, the established hospital messaging format |

Both are recorded as disclosures of patient information.

## Corrections

A released report cannot be quietly edited. Correcting one means issuing an
[amended report](/help/reporting/amended-reports/), which retains the original
value and marks the report as amended.
