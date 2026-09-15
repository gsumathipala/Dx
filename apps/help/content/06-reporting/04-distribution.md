---
title: Report distribution
summary: Getting reports to requesters, delivery preferences, and confirming they arrived.
audience: clerk, manager
keywords: distribution, delivery, email, fax, requester, portal, queue
---

## Requesters

**Settings → Requester registry** records who sends work: general practitioners,
wards, clinics, hospitals and referring laboratories, with contact details and a
**delivery preference**.

| Preference | Notes |
| --- | --- |
| **Portal** | The requester views reports in the system |
| **Email** | Requires an address; consider encryption |
| **Print** | Posted or collected |
| **Fax** | Still in use in many settings |
| **HL7 interface** | Direct delivery into their system |

Keeping the registry current is unglamorous and matters: a report sent to a
clinician who left last year has not been delivered, and nobody knows.

## Distribution rules

**Settings → Distribution rules** decide how a given requester's reports are
delivered, optionally per test. **Auto release** sends as soon as the report is
clinically verified.

## The delivery queue

**Report delivery** shows outbound reports with status and any error, plus the
distribution log.

Check **failed** deliveries daily. A failure is a report a clinician is waiting
for and has not received — and unlike a system error, nobody is looking at a
screen wondering where it is.

## Sending patient information by email

Ordinary email is not confidential. It crosses servers you do not control and
rests on them.

Where reports go by email:

- Use an encrypted channel or an encrypted attachment.
- Confirm the address belongs to the intended recipient.
- Keep the body minimal — a notification that a report is available, with the
  detail behind authentication, is safer than the report itself.

Both HIPAA and GDPR treat an unencrypted email of patient data as a disclosure
you must be able to justify.

## Confirming receipt

For critical results, delivery is not the point — **receipt** is. That is why a
critical value requires a telephone call with
[read-back](/help/clinical-decision-support/critical-values/), not a report.
