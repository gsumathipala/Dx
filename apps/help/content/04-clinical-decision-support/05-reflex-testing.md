---
title: Reflex testing
summary: Adding a follow-on test automatically when a result warrants it, and how to configure rules safely.
audience: scientist, manager
keywords: reflex, cascade, add-on, automatic, rules, algorithm
---

## What reflex testing is

A reflex test is one the laboratory adds **itself**, without a new request,
because a result warrants it.

The classic: a raised TSH reflexes free T4. TSH alone cannot distinguish
primary hypothyroidism from other causes; adding free T4 answers the question
on the same specimen, with no second appointment and no second venepuncture.

## Why it is worth doing

| Benefit | Why |
| --- | --- |
| **Speed** | The answer arrives in one episode, not two |
| **Fewer visits** | The specimen is already in the laboratory |
| **Consistency** | The algorithm fires every time, not when someone remembers |
| **Appropriateness** | The second test is only done when it is indicated |

Reflex testing is one of the few interventions that improves care and reduces
cost simultaneously — it replaces *always* testing with *testing when the first
result says so*.

## Common algorithms

| First test | Condition | Reflexes to |
| --- | --- | --- |
| TSH | Outside interval | Free T4 |
| Total calcium | Abnormal | Albumin, for correction |
| Positive screening immunoassay | Reactive | Confirmatory assay |
| Urine dipstick | Nitrite or leucocytes positive | Culture |
| Protein electrophoresis | Paraprotein band | Immunofixation |
| Raised creatinine | Above threshold | eGFR (calculated) |

## Configuring a rule

**Settings → Reflex testing rules.** A rule names the trigger test, the
condition (`>`, `>=`, `<`, `<=`, `==`) and threshold, and the test to add.

A rule fires **once per order**. It cannot fire twice on the same order, and it
cannot add the test that triggered it — which would loop.

## Getting it right

**Agree it clinically.** A reflex rule is a laboratory-initiated clinical
decision. Agree it with the clinicians who receive the results, and document
the agreement. A test appearing on a report nobody ordered, with nobody having
agreed it should, is a complaint waiting to happen.

**Watch the threshold.** Too sensitive and you add tests constantly; too
specific and you miss the cases the rule exists for.

**Check the specimen supports it.** The reflexed test must be performable on
the specimen already collected, within its stability window. A reflex requiring
a specimen type you do not have simply produces a request nobody can fill.

**Consider the cost and the report.** A reflexed test is billable work and
appears on the report. Both need to be expected.

## What happens when a rule fires

The reflexed test is added to the order and appears in result entry alongside
the rest. A record of the activation is kept: which rule, what value triggered
it, when.

The added test still goes through the same workflow — entered, validated,
verified — like any other. A reflexed result is not auto-released.
