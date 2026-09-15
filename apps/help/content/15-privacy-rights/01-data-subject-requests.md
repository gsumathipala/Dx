---
title: Data subject requests
summary: What a patient can ask for, what you must give them, and what you must refuse.
audience: manager, medic
keywords: GDPR, subject access, erasure, portability, restriction, article 15, article 17, tutorial
---

## What a patient can ask

Under GDPR — and in similar form under several other regimes — a patient can
ask you to:

| Right | Article | What it means |
| --- | --- | --- |
| **Access** | 15 | Give me a copy of everything you hold about me |
| **Rectification** | 16 | Correct what is wrong |
| **Erasure** | 17 | Delete it |
| **Restriction** | 18 | Stop using it, but keep it |
| **Portability** | 20 | Give it to me in a form another system can load |
| **Objection** | 21 | Stop processing it for this purpose |
| **Human review** | 22(3) | A person, not a machine, should decide this |

Each has a deadline: **one month**, extendable by two further months for a
complex request, provided you tell the patient inside the first month.

## The two rules that matter most

### Log it the day it arrives

The clock runs from **receipt**, not from when you verify who is asking. A
laboratory cannot extend its own deadline by being slow to check identity.

### Verify identity before anything leaves

Nothing is exported or erased until you record what you checked. A data subject
request is the easiest way in the world to obtain somebody else's medical
record — "I'd like a copy of my results, here is the name and date of birth"
is not a credential.

Record what you actually checked: *"Passport seen in person by
A. Nolan, 15 September"*, or *"Known to the renal team; identity confirmed by
telephone against three data items"*. **Never upload a copy of the document** —
that creates a second, worse copy of their identity papers.

## Tutorial: handling a subject access request

### 1. Log it

**Settings → Data subject requests**. Fill in the patient's MRN, the right
being exercised, who asked, and their relationship to the patient.

You get a reference — `DSR-2026-0003` — and a due date.

### 2. Verify identity

On the request's page, record how identity was established. The request becomes
actionable.

### 3. Produce the export

**Produce the export.** Set a passphrase — at least twelve characters. The
export is encrypted with AES-256-GCM.

The passphrase is **not stored** and cannot be recovered. Give it to the patient
by a different channel from the file itself: the file by secure portal, the
passphrase by telephone.

### 4. What they get

| Right | Format |
| --- | --- |
| Access (Art. 15) | A full document: demographics, every order and result, the disclosures made, the purposes of processing, the retention position, and a statement of where automatic verification was used |
| Portability (Art. 20) | A FHIR R4 Bundle another system can load |

The Article 15 export includes a declaration of **automated decision-making**,
because Article 15(1)(h) requires it and [autoverification is exactly
that](/help/rules-and-automation/autoverification/). It says how many of their
results were released by a rule, and that any of them can be reviewed by a
person on request.

### 5. Download and send

The encrypted file is downloadable from the request's page.

---

## Tutorial: handling an erasure request

**You will usually refuse, and refusing is the correct answer.**

### Why

Laboratory records must be kept for their statutory period. CLIA §493.1105
requires two years for test records and ten for pathology reports; local rules
are often longer. GDPR Article 17(3) disapplies the right to erasure exactly
where a legal obligation (17(3)(b)) or a public health interest (17(3)(c))
requires retention.

Deleting on request would destroy records you are legally required to hold, and
would do it irreversibly.

### What the screen does

Open the request. It assesses **every order, one at a time**, against your
retention schedule and shows you:

> 2 order(s) past retention and erasable; 5 retained.
>
> * Erasure is refused for the records listed below. GDPR Article 17(3)(b)
>   disapplies the right to erasure where processing is necessary for
>   compliance with a legal obligation…
> * 2026-03-04-0012: retained until 2028-03-04 under the laboratory's retention
>   schedule for test record / result (2 years, CLIA 42 CFR §493.1105).

### Acting on it

Press **Erase what may lawfully be erased**. The expired records have their
clinical content destroyed; the retained ones are untouched.

The **shell** of an erased record stays — accession number, dates, the fact of
erasure. The audit trail refers to those records, and a trail that can be
broken by a deletion request is not an audit trail.

Identifiers (name, contact details) are removed only when **nothing clinical is
retained**.

### Telling the patient

The refusal basis is recorded on the request, with the specific period and
authority for each retained record. That is what Article 12(4) asks you to give
them: not "no", but "no, because, until when".

---

## Restriction (Article 18)

Flags the patient's data as restricted. Recorded, visible, and enforced —
except for clinical care, which continues.

That exception is Article 18(2), and it is not a loophole. A restriction that
stopped a clinician seeing a result would endanger the person it exists to
protect.

## Rectification (Article 16)

**Do not use this screen.** A clinical record is corrected by
[amendment](/help/reporting/amended-reports/): the original value stays
visible, the correction is signed, and anyone who received the original is
notified.

That happens to be what CAP requires anyway, and it satisfies Article 19's
notification duty at the same time.

## Human review (Article 22)

If a patient objects to a result having been released without a person reading
it, override the automatic verification from **Settings → Rule firing log**.
The result returns to the worklist for a person to verify.

## Overdue requests

A request past its deadline appears on the [exception
queue](/help/rules-and-automation/exception-queue/). Take the extension before
that happens if you can see it coming, and record why — the patient must be
told within the first month, and the system will not do that for you.
