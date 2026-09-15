---
title: Why a rules engine
summary: What laboratory knowledge looks like when it is written down as data instead of living in somebody's head.
audience: scientist, medic, manager
keywords: rules engine, autocommenting, interpretive comment, knowledge, tutorial
---

## The problem

Every laboratory knows things it has never written down.

*A potassium of 6.4 on a sample that took four hours to arrive is probably
pseudohyperkalaemia, not hyperkalaemia.* *A TSH of 6.2 in an eighty-year-old is
a different conversation from the same number in a thirty-year-old.* *An
alkaline phosphatase three times the upper limit in a growing adolescent is
bone, not liver.*

That knowledge lives in three places, all of them bad:

1. **In somebody's head.** It leaves when they do, and it is applied
   inconsistently by everybody else.
2. **On a laminated sheet by the bench.** Nobody reads it after the first week,
   and nobody updates it.
3. **Hard-coded in the software.** Changing it needs a developer, a release and
   a validation cycle, so it never changes.

A rules engine is the fourth option: the knowledge is **data**, written by the
laboratory, versioned, approved, testable and auditable.

## What a rule is

Two halves.

**When** — a set of conditions over the facts available at the moment a result
is produced.

**Then** — a list of things to do when they hold.

That is it. The expressiveness is deliberately limited: conditions are ANDed
within a group and ORed across groups, with no parentheses, no nesting and no
expression language.

## Why so simple

Because a rule nobody can read is a rule nobody can validate, and an
unvalidatable rule is a CLIA finding.

An expression language would let you write rules a biomedical scientist cannot
check at a glance. In the ten years those rules run, nobody will check them.
When a report says something surprising, nobody will be able to explain why.

Grouped AND/OR conditions render as a form. A senior scientist can read the
whole rule in five seconds and say "no, that is wrong, it should be *or*". That
conversation is the entire point.

## What rules are used for here

| Use | Example |
| --- | --- |
| **Interpretive comments** | "Consider a fasting sample" on a raised random glucose |
| **Suppression notes** | "Potassium may be falsely elevated — haemolysed specimen" |
| **Flagging** | Add a *Review* flag on anything a senior should see |
| **Reflex testing** | Add HbA1c when glucose exceeds a threshold |
| **Escalation** | Raise an exception queue item when something looks wrong |
| **Notification** | Message the duty biochemist |
| **Automatic release** | Send out the normal ones without a person reading them |

The last one is different in kind from the rest, and has [its own
topic](/help/rules-and-automation/autoverification/).

## What rules are *not* for

**A rule is not a diagnosis.** An interpretive comment tells a clinician
something about the *specimen and the measurement*. It does not tell them what
is wrong with their patient. "Consider a fasting sample" is laboratory advice;
"this patient has diabetes" is not yours to say from a single glucose.

**A rule is not a substitute for a reference interval.** If you find yourself
writing a rule that says "flag this when it is above 7", the reference interval
is wrong. Fix the interval.

**A rule is not a workaround for a broken control.** If QC lockout is stopping
work, a rule that releases results anyway does not exist — and would not be
built if it were asked for.

## Where to start

Read [writing a rule](/help/rules-and-automation/writing-a-rule/) next, then
[approving and validating one](/help/rules-and-automation/approving-a-rule/).
