---
title: What Dx is
summary: What a laboratory information system does, and what this one does in particular.
audience: everyone
keywords: lis, overview, introduction, workflow
---

## What a laboratory information system is for

A clinical laboratory turns a tube of blood into a number a clinician can act
on. Between those two points sit a dozen steps where the wrong thing can
happen: the tube can be mislabelled, the analyser can drift, the result can be
transcribed wrongly, the report can go to the wrong doctor, or a
life-threatening value can sit unnoticed in a queue.

A laboratory information system (LIS) is the record of that journey and the set
of checks along it. It answers four questions, permanently:

- **Whose sample is this?** Identity, from collection to disposal.
- **What was done to it?** Which tests, on which instrument, by whom, when.
- **Is the answer trustworthy?** Was quality control acceptable, was the
  analyst competent, did a second person check it.
- **Who saw it, and when?** Because a result that nobody acted on is a result
  that did not help anyone.

## The three phases

Laboratory work is conventionally divided into three phases, and most errors
are not where people expect.

| Phase | What happens | Share of errors |
| --- | --- | --- |
| **Pre-analytical** | Ordering, collection, transport, reception, preparation | roughly 60–70% |
| **Analytical** | The measurement itself | roughly 10–15% |
| **Post-analytical** | Reporting, interpretation, communication | roughly 20–25% |

Those proportions are consistent across decades of published error studies. The
measurement — the part with the expensive instrument — is the *least* error-prone
step. This is why Dx puts as much structure around accessioning, specimen
reception and result communication as it does around the analyser interface.

## What Dx does

**The workflow** — patient registration, accessioning with collision-safe
numbering, specimen reception and rejection, phlebotomy rounds, result entry,
two-stage authorisation, and printable reports carrying their signatures.

**Clinical decision support** — reference intervals that account for age and
sex, delta checks against the patient's own history, critical value detection
with documented read-back, reflex testing, calculated analytes, and notifiable
disease surveillance.

**Quality** — Westgard multirule quality control with Levey-Jennings charts,
instrument maintenance and calibration records, proficiency testing, method
validation, nonconformance management and a risk register.

**A permanent record** — every change to anything, captured automatically,
cryptographically chained so it cannot be altered afterwards.

**Connections** — analysers over ASTM and HL7, and export to other systems as
FHIR or HL7.

## What Dx is not

Stated plainly, because an overstated claim is worse than a gap:

- It is **not a validated medical device**. A laboratory deploying it must
  perform its own installation, operational and performance qualification.
- It does **not** interpret results for you. It flags, it computes, it
  compares — a qualified person decides.
- It does not cover **transfusion medicine**, electronic prescribing, or
  billing claim submission.

## How this help library is arranged

Each topic tells you three things: what a screen does, how to use it, and the
laboratory practice behind it. Where a rule comes from a regulation, the topic
names the regulation and explains why it exists — so when the system refuses
something, you can tell a deliberate control from a bug.

> **Next:** [Signing in and your account](/help/getting-started/signing-in/)
