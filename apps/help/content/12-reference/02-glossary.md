---
title: Glossary
summary: Laboratory, quality and regulatory terms used throughout the system.
audience: everyone
keywords: glossary, terms, definitions, abbreviations, jargon
---

## Laboratory

**Accession number** — the unique identifier given to a request when it is
registered, following the specimen thereafter. Format `YYYY-MM-DD-NNNN`.

**Aliquot** — a portion taken from a parent specimen, for referral, storage or
to avoid repeated freeze–thaw.

**Analyte** — the substance being measured.

**Analytical phase** — the measurement itself. Roughly 10–15% of laboratory
errors.

**Chain of custody** — the unbroken record of who held a specimen and when.

**Haemolysis** — rupture of red cells, releasing intracellular contents. Falsely
raises potassium, LDH and AST.

**Icterus / lipaemia** — yellow or milky sample appearance, from bilirubin or
lipid, both of which interfere optically.

**MRN** — medical record number; the patient's unique identifier.

**Post-analytical phase** — reporting and communication. Roughly 20–25% of
errors.

**Pre-analytical phase** — ordering through to preparation for analysis.
Roughly 60–70% of errors.

**Reflex test** — a test the laboratory adds itself because a result warrants
it.

**STAT** — immediate priority.

**TAT** — turnaround time.

## Quality

**Accuracy** — closeness to the true value. Opposed to *precision*.

**Bias** — systematic difference from the true value.

**Calibration** — establishing the relationship between instrument signal and
concentration.

**CAPA** — corrective and preventive action.

**Correction vs corrective action** — correction fixes the instance; corrective
action stops recurrence.

**CV** — coefficient of variation; standard deviation as a percentage of the
mean.

**CVa / CVi** — analytical imprecision; within-subject biological variation.

**EQA** — external quality assessment. See *proficiency testing*.

**Levey-Jennings chart** — control values plotted over time against mean and
standard deviations.

**Precision** — reproducibility on repetition. A method can be precisely wrong.

**Proficiency testing** — analysis of specimens from an outside provider,
compared with peers. Detects bias that internal QC cannot.

**Quality control** — analysis of material of known value alongside patients.

**RCV** — reference change value; the change between two results unlikely to be
chance.

**Reportable range** — the span over which a method is linear and trustworthy.

**Root cause** — the underlying reason, usually a process, not a person.

**Westgard rules** — a multirule scheme for interpreting QC.

**z-score** — how many standard deviations a result sits from the assigned
value.

## Clinical decision support

**Critical value** — a result representing an immediate threat to life,
requiring the clinician be told now.

**Delta check** — comparison with the patient's own previous result.

**Panic limit** — the threshold defining a critical value.

**Read-back** — the receiver repeating a result back to confirm it was heard
correctly.

**Reference interval** — the central 95% of results from a healthy reference
population. Not a boundary between health and disease.

## Interoperability

**ASTM E1381 / E1394** — the older instrument protocol: framing, and record
content.

**FHIR** — modern healthcare interoperability standard; JSON resources over
HTTP.

**HL7 v2** — long-established hospital messaging: pipe-delimited segments.

**LOINC** — universal codes identifying what was measured, across six axes.

**MLLP** — Minimal Lower Layer Protocol; how HL7 v2 is framed over TCP.

**ORU / ORM / ADT** — HL7 message types: results, orders, admission/discharge.

**SNOMED CT** — clinical terminology for findings and diagnoses.

**UCUM** — unambiguous codes for units of measure.

## Regulatory

**CAP** — College of American Pathologists; accreditation with peer inspection.

**CLIA** — US federal law governing laboratory testing.

**Deemed status** — accreditation recognised as satisfying CLIA.

**GDPR** — EU data protection regulation.

**HIPAA** — US law on privacy and security of health information.

**ISO 15189** — international standard for medical laboratories.

**Minimum necessary** — access limited to what a role requires.

**PHI** — protected health information.

**21 CFR Part 11** — FDA rules on electronic records and signatures.

## System

**Append-only** — records can be added, never changed or removed.

**Audit trail** — the permanent record of every change.

**Electronic signature** — an authorisation attributable to a named person,
applied with re-authentication.

**Hash chain** — each entry embedding the previous entry's hash, making
tampering detectable.

**Installer** — the role holding system authority and no clinical access.

**Redaction** — showing a record with its confidential content removed.
