---
title: Privacy, consent and disclosure
summary: What is recorded when you open a record, what consent covers, and a patient's rights over their data.
audience: everyone
keywords: hipaa, gdpr, privacy, consent, disclosure, phi, confidentiality
---

## Looking at a record is recorded

Every time you open a patient record, a report, or a result entry screen, the
system records that you did: who, which patient, when, from which address.

This is not suspicion of staff. It is a legal requirement — HIPAA
§164.312(b) requires audit controls over systems holding protected health
information — and it protects you as much as the patient. If a record is
improperly accessed, the log shows who did and, just as importantly, who did
not.

Administrators can review this at **Settings → PHI access log**.

## Minimum necessary

You should access the records you need for the work in front of you, and no
others. HIPAA phrases this as the *minimum necessary* standard
(45 CFR §164.502(b)).

In practice: do not look up a colleague, a neighbour or a public figure out of
curiosity. It is visible, and it is a disciplinary and legal matter in every
jurisdiction Dx is designed for.

The system applies the same principle to itself — the **installer** role
maintains the system and cannot open a patient record at all.

## Consent

A patient's consent for particular uses of their data is recorded against them:

| Kind | Covers |
| --- | --- |
| Treatment | Ordinary diagnostic use |
| Research | Use of samples or data in research |
| Data sharing | Sharing beyond the treating team |
| Genetic | Genetic testing specifically |
| Marketing | Contact for non-clinical purposes |

Consent can be withdrawn; the record keeps both the grant and the withdrawal,
because "when did they withdraw?" is as important as "did they?".

## Accounting of disclosures

Where information goes **outside** treatment, payment and routine operations,
the disclosure is recorded: who received it, when, for what purpose, and
whether the patient authorised it.

HIPAA §164.528 gives a patient the right to ask for an accounting of
disclosures covering the previous six years. **Settings → Disclosure
accounting** is that record.

Public health reporting is a disclosure and is recorded as one — it is
permitted without consent, but it still has to be accounted for.

## Break the glass

Occasionally someone must access a record they would not normally reach — an
emergency, an unconscious patient. Such access is flagged as an emergency
override rather than blocked, and reviewed afterwards.

The principle: never let a control cause harm in an emergency, but never let an
emergency go unexamined.

## GDPR

For laboratories in scope of GDPR, health data is a special category
(Article 9) with a higher bar for processing. Patients have rights of access,
rectification, erasure, restriction and portability.

> **Erasure is not absolute.** Article 17(3) excludes data a controller must
> retain for legal obligations or public-health reasons. Laboratory records are
> retained under CLIA 42 CFR §493.1105, so a request to erase them cannot
> generally be honoured while that period runs. Consult your data protection
> officer — do not delete records on request without doing so.

## If you suspect a breach

Tell your laboratory manager or data protection officer **immediately**.
Breach notification deadlines are short — 72 hours under GDPR — and the clock
starts when the organisation becomes aware, not when it finishes investigating.

Do not attempt to fix it by deleting anything. The audit trail is designed to
be permanent, and an attempt to alter it will be visible.
