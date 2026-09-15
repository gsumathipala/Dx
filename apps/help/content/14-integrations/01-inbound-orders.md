---
title: Orders arriving from the hospital
summary: HL7 order and patient messages, what they do, and what happens when one is refused.
audience: manager, clerk, scientist
keywords: HL7, ORM, ADT, inbound, order entry, merge, tutorial, integration
---

## The point

The largest single source of transcription error in a laboratory is somebody
retyping a request that another system already holds. Inbound order messages
remove that step: the hospital's order-entry system sends the request, and it
is accessioned without anyone touching a keyboard.

It also removes the wait. Accession-to-result time in most sites is dominated
by clerical work, not by analysis.

## What arrives

| Message | Effect |
| --- | --- |
| `ORM^O01`, `OML^O21` (`ORC-1 = NW`) | A new order is accessioned |
| `ORM^O01` (`ORC-1 = CA`) | The matching order is cancelled |
| `ADT^A01`, `A04`, `A05`, `A08`, `A28`, `A31` | A patient is registered or updated |
| `ADT^A40` | Two patient identifiers are merged |

## What you will notice

**Orders appear on the worklist** without being keyed. They carry the placer
order number from the sending system, so a cancellation later finds the right
order.

**Patients are created or updated** from the same message. You may see a
patient registered a moment before their order arrives.

**Diagnosis codes arrive too**, from `DG1` segments, and become ICD-10 codes on
the order. The decision rules can then use them — "a sodium of 128 on a patient
already coded E87.1" is a different comment from the same number with no
context.

## Identity: MRN and nothing else

A patient is matched on their medical record number. Not on name, not on date
of birth, not on any combination.

This is deliberate and occasionally inconvenient. Matching on name and date of
birth would eventually merge two different people who share both — which
happens far more often than intuition suggests, and is unrecoverable once
results are attached to the merged record.

A message with no MRN is refused.

## A new patient needs a date of birth

An `ADT` that would create a patient without one is refused. Age drives
reference intervals, critical limits and several decision rules; registering
somebody without a date of birth silently degrades all three, and silence is
the problem.

An update to an existing patient does not need one.

## Merges

`ADT^A40` moves orders from a retired MRN onto a surviving one.

The retired patient record is **kept**, flagged as merged, not deleted. Reports
were issued under that number and the audit trail refers to it. A trail with
dangling references is not a trail.

## When a message is refused

Every inbound message is acknowledged. There are three answers:

| ACK | Meaning | What the sender should do |
| --- | --- | --- |
| `AA` | Accepted and applied | Nothing |
| `AE` | Understood and refused | Fix the content; do not retry unchanged |
| `AR` | Could not be parsed | Fix the message structure |

`AE` and `AR` are kept distinct on purpose. Conflating them is why integration
failures take days to diagnose — a sender that cannot tell "your data is wrong"
from "your message is broken" retries forever.

**A refused message raises an item on the [exception
queue](/help/rules-and-automation/exception-queue/)**, so somebody sees it. An
integration failure that lives only in a log file is an integration failure
nobody knows about.

## Duplicates

An order retransmitted with a placer number that already exists is
acknowledged as a duplicate and **does not** accession a second specimen.
Integration engines retransmit; a system that made two specimens from two
copies of one request would have somebody drawing blood twice.

## Setting it up

Your integration engine posts the raw message to
`POST /api/middleware/hl7/` with the shared instrument token in an
`Authorization: Bearer` header. See
[API.md](/help/integrations/the-rest-api/) for the detail, and your
administrator for the token.
