---
title: Change control
summary: Recording system and method changes, and why validation evidence is required.
audience: manager, administrator
keywords: change control, validation, part 11, 11.10, software, configuration
---

## Why record changes

A validated system is validated **as configured**. Change the configuration and
you have a different system, whose behaviour has not been demonstrated.

> **21 CFR Part 11 §11.10(a)** requires validation of systems to ensure
> accuracy, reliability and consistent intended performance, including the
> ability to discern altered records.
> **ISO 15189 §8.2** requires control of changes to the management system.

## What warrants a record

| Change | Record? |
| --- | --- |
| Software upgrade | Yes |
| New or changed instrument interface | Yes |
| Change to a reference or critical limit | Yes |
| New or changed clinical rule | Yes |
| New test in the catalogue | Yes |
| Change to an enforced control | Yes |
| Adding a user | No — the audit trail covers it |
| Routine maintenance | No — the equipment log covers it |

The test: **could this change what a result says, or who may authorise it?**

## The record

**Settings → Change control**: reference, title, description, type, impact
assessment, validation evidence, rollback plan, and status through
Requested → Assessed → Approved → Implemented → Verified.

A change cannot be marked **Implemented** or **Verified** without validation
evidence. Recording that something was done without recording that it worked is
the gap this control exists to close.

## The elements that matter

**Impact assessment.** What could this affect? A reference interval change
affects flagging, delta checks, and possibly critical value detection. Thinking
it through beforehand is where most bad changes are caught.

**Validation evidence.** What did you check afterwards? For an interval change,
test results either side of the new boundary and confirm flagging. For an
interface change, send known messages and confirm what arrives.

**Rollback plan.** What if it is wrong? Often "revert the setting", which is
fine — but say so, because knowing it is reversible is part of assessing the
risk.

## Approval

Separate the person requesting from the person approving. Someone other than
the implementer should agree it is safe — the same second-pair-of-eyes
principle as result verification, and for the same reason.

## Changes do not act retrospectively

A new rule applies to results entered **after** it. Changing a critical limit
does not re-examine yesterday's results.

If a limit was wrong and results were released against it, that is a
nonconformance and possibly an amended report — not something the configuration
change fixes.
