---
title: PHI access logging and disclosure
summary: What is recorded when patient data is viewed or released, and who reviews it.
audience: administrator, manager
keywords: phi, hipaa, access log, disclosure, accounting, 164.528, privacy
---

## Two different records

**PHI access log** — who *looked at* identifiable patient information.
**Disclosure accounting** — where patient information *went* outside the
laboratory.

They answer different questions and are kept separately. Reads vastly outnumber
disclosures, and they are retained on different schedules.

## The access log

Every view of a patient record, a report, result entry, or a FHIR or HL7 export
records: the user, the patient, the time, the path, the purpose, the IP address,
and whether it was an emergency override.

> **HIPAA §164.312(b)** requires audit controls recording activity in systems
> containing electronic protected health information.

**Settings → PHI access log** (administrators) reviews it.

### Why keep a separate log

Writes go into the hash-chained audit trail. Reads do not, for a practical
reason: in any clinical system reads outnumber writes by orders of magnitude,
and folding them into the chain would bury the record of actual changes.

Keeping them apart means the change history stays legible while access is still
fully recorded.

### Reviewing it

Look for patterns, not individual entries:

- Access to a record by someone with no connection to that patient's care
- Bursts of access outside working hours
- Repeated access to one patient by one person
- Access to a record with no corresponding order

Most of what looks suspicious is explicable, and looking is the point. An
unreviewed log satisfies nobody.

## Disclosure accounting

Disclosures **outside** treatment, payment and routine operations are recorded:
patient, recipient, date, purpose, what was disclosed, and whether the patient
authorised it.

> **HIPAA §164.528** gives a patient the right to an accounting of disclosures
> covering the previous six years.

| Purpose | Notes |
| --- | --- |
| Treatment, payment, operations | Not generally accountable |
| Public health reporting | Accountable; permitted without consent |
| Legal or court order | Accountable |
| Patient request | Accountable |
| Research | Accountable; usually needs consent or a waiver |

A notifiable disease report is a disclosure and is recorded as one. Permitted is
not the same as unrecorded.

## Break the glass

Emergency access is flagged rather than blocked, and reviewed afterwards.

Never let a control cause harm in an emergency; never let an emergency go
unexamined. Both halves matter — a break-the-glass facility nobody reviews is
simply an unlocked door.

## Minimum necessary

Access only what the work in front of you requires. HIPAA states it as a
standard (45 CFR §164.502(b)); Dx applies it structurally with the
[installer role](/help/security-and-audit/the-installer-account/), which
maintains the system and cannot read a patient record at all.
