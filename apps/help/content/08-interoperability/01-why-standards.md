---
title: Why interoperability standards exist
summary: What goes wrong without them, and what each standard is actually for.
audience: scientist, manager, administrator
keywords: interoperability, standards, hl7, fhir, loinc, snomed, astm
---

## The problem

A laboratory result has to travel: from an analyser into the LIS, from the LIS
into a hospital record, sometimes onward to a registry or another laboratory.
Every hop is a chance to lose meaning.

Without agreed standards, each connection is bespoke. Thirty analysers and five
hospital systems means up to 150 one-off integrations, each breaking whenever
either end changes.

Worse, meaning degrades. Your "GLU" and another system's "GLUC" may both be
glucose — or one may be fasting and the other random. A number arriving without
agreement on **what was measured**, **in what units**, and **on what specimen**
is not information.

## Two problems, two kinds of standard

**Transport** standards say how a message is structured and moved: ASTM, HL7 v2,
FHIR.

**Terminology** standards say what the contents *mean*: LOINC for observations,
SNOMED CT for clinical findings, UCUM for units.

You need both. A perfectly formed HL7 message carrying a local code nobody else
recognises has moved data without moving meaning.

## The standards in practice

### ASTM E1381 / E1394

The older instrument protocol, still ubiquitous. A character-oriented format
with records for header, patient, order, result and terminator, wrapped in a
checksummed frame with an ENQ/ACK handshake.

Simple, robust over a serial line, and unaware of anything beyond the analyser
and the LIS.

### HL7 version 2

The workhorse of hospital messaging since the late 1980s. Pipe-delimited
segments — `MSH`, `PID`, `OBR`, `OBX` — carrying orders (`ORM`), results
(`ORU`) and admissions (`ADT`).

Enormously widely deployed, and famously flexible: so many fields are optional
that two conforming systems often cannot exchange messages without a
site-specific mapping. "HL7 compliant" means less than it sounds.

### FHIR

The modern successor: resources (`Patient`, `Observation`,
`DiagnosticReport`) exchanged as JSON over HTTP, with the conventions of the
web — URLs, REST, standard authentication.

Far easier to work with and far better suited to applications and portals. Still
being adopted; most hospitals run both FHIR and HL7 v2 for years.

### LOINC

A universal code for *what was measured*. LOINC identifies an observation by six
axes: component, property, time aspect, system (specimen), scale and method.

That precision is the point. "Glucose" is ambiguous — LOINC distinguishes
fasting plasma glucose from a two-hour post-load value from cerebrospinal fluid
glucose, because they are different observations with different meanings.

Coding your catalogue to LOINC is what lets another system interpret your
results without a bespoke mapping.

### UCUM

Unified Code for Units of Measure. Unambiguous unit strings — `mmol/L`,
`10*9/L` — so a receiving system can convert safely rather than guessing.

## What Dx does

| Direction | Standard |
| --- | --- |
| Analyser → Dx | ASTM E1381/E1394, HL7 v2 over MLLP |
| Dx → other systems | FHIR R4, HL7 v2 ORU^R01 |
| Coding | LOINC on test definitions |

Inbound orders (`ORM`) and admissions (`ADT`) are **not** implemented. Orders
are entered in Dx or arrive by other means.
