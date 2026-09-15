---
title: The regulations, in plain terms
summary: What CLIA, CAP, ISO 15189, 21 CFR Part 11 and HIPAA each require, and where Dx addresses them.
audience: manager, administrator
keywords: clia, cap, iso 15189, part 11, hipaa, gdpr, regulation, compliance, accreditation
---

## CLIA — Clinical Laboratory Improvement Amendments

**What it is.** US federal law, 42 CFR Part 493, applying to any laboratory
testing human specimens for health assessment. Not accreditation — law.
Non-compliance can stop a laboratory operating.

**What it requires**, and where Dx addresses it:

| Requirement | Section | In Dx |
| --- | --- | --- |
| Personnel qualifications and competency | §493.1451 | Competency records; gating of validation |
| Quality control | §493.1256 | Westgard evaluation; QC lockout |
| Proficiency testing | §493.801 | PT surveys, results, attestation |
| Method validation | §493.1253 | Four elements before approval |
| Instrument maintenance | §493.1254 | Equipment records, calibration dates |
| Independent result review | §493.1495 | Self-verification block |
| Record retention | §493.1105 | Retention schedule |

## CAP — College of American Pathologists

**What it is.** A voluntary accreditation programme with detailed checklists and
peer inspection every two years. CAP accreditation confers CLIA deemed status.

**Where it goes beyond CLIA.** More prescriptive on documentation, and explicit
about things CLIA leaves implicit:

- **Critical value read-back** (GEN.41320) — documenting that the receiver
  repeated the result back.
- **Amended reports** — retaining the original, marking the report, notifying
  the clinician.
- Detailed expectations on document control and competency evidence.

## ISO 15189

**What it is.** The international standard for medical laboratories, covering
both quality management and technical competence. Structured around processes
and risk rather than prescriptive rules.

**What it adds**, and where Dx addresses it:

| Requirement | Clause | In Dx |
| --- | --- | --- |
| Document control | §8.3 | Versioned documents, review dates, acknowledgement |
| Nonconformity and corrective action | §8.7 | CAPA with root cause and effectiveness check |
| Risk management | §8.5 | Risk register with residual scoring |
| Control of changes | §8.2 | Change control records |

The 2022 revision strengthened risk management considerably — risk is now a
thread through the whole standard rather than a clause.

## 21 CFR Part 11

**What it is.** FDA rules on electronic records and signatures, applying where
FDA-regulated records are kept electronically. Relevant to clinical laboratories
in trials, and widely adopted as good practice elsewhere.

| Requirement | Section | In Dx |
| --- | --- | --- |
| System validation | §11.10(a) | Change control with validation evidence |
| Audit trail | §11.10(e) | Hash-chained, append-only, with previous values |
| Access limited to authorised individuals | §11.10(d) | Named accounts, roles, PHI barrier |
| Signature manifest | §11.50 | Printed name, time, meaning, on the report |
| Signature linked to its record | §11.70 | Content hash bound to the signature |
| Signature components | §11.200 | Password re-entry at signing |
| Password controls | §11.300 | Ageing, history, lockout |

## HIPAA

**What it is.** US law on the privacy and security of protected health
information. Two rules matter here: **Privacy** (what may be used and disclosed)
and **Security** (safeguards for electronic PHI).

| Requirement | Section | In Dx |
| --- | --- | --- |
| Audit controls | §164.312(b) | PHI access logging |
| Automatic logoff | §164.312(a)(2)(iii) | Idle session termination |
| Encryption | §164.312(a)(2)(iv), (e)(2)(ii) | AES-256-GCM for archives and exports |
| Minimum necessary | §164.502(b) | Roles; the installer's PHI barrier |
| Accounting of disclosures | §164.528 | Disclosure records, six years |
| Public health disclosure | §164.512(b) | Notifiable condition reporting |

## GDPR

**What it is.** EU regulation on personal data. Health data is a special
category under Article 9 with a higher bar for processing.

Patient rights: access, rectification, erasure, restriction, portability.

> **Erasure is not absolute.** Article 17(3) excludes data retained for a legal
> obligation or for public health. Laboratory records held under a retention
> requirement fall within that exclusion. Consult your data protection officer
> before deleting anything on request.

Article 32 requires appropriate security including encryption and the ability to
restore availability after an incident — which is a backup regime you have
actually tested.

## How they overlap

Substantially. A laboratory meeting ISO 15189 meets most of CLIA; the difference
is in evidence and emphasis, not intent.

The common thread across all of them is the same: **be able to show what you
did, why, and that it was done by someone competent.** Almost every specific
requirement is a form of that.

## What Dx does not do

- It is **not a validated medical device**. Your installation, operational and
  performance qualification is your responsibility.
- Transfusion medicine (21 CFR 606, AABB) is not implemented.
- It does not make you compliant. Software is one part; personnel, premises,
  procedures and your own validation are the rest.
