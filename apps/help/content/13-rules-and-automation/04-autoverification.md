---
title: Autoverification
summary: Releasing normal results without a person reading them — what it does, every guardrail it passes, and how to take one back.
audience: scientist, medic, manager
keywords: autoverification, automatic release, guardrails, CLIA 493.1291, CLSI AUTO10, override, tutorial
---

## Why do this at all

A busy chemistry laboratory produces results faster than anyone can read them.

A scientist who must click through four hundred normal potassiums to reach the
one that matters is being trained, by the system, not to look. The four
hundredth click is not a review; it is a reflex. Releasing the
obviously-normal automatically is how the abnormal gets genuine attention.

CLSI AUTO10-A and CLIA §493.1291 both treat autoverification as legitimate.
Neither treats it as free.

## What it does not do

**Autoverification never relaxes an existing control.** Everything a human
verifier must satisfy, a rule must satisfy too — and a rule may additionally
not touch anything a person would want to look at.

## Every guardrail

A result is released automatically **only if all of the following hold.**

### 1. The laboratory has approved that analyte

`auto verify permitted` on the test definition, off by default. No rule can
release a test the laboratory has not separately validated and ticked.

This is the most important guardrail and the easiest to skip past. It exists
because autoverification is an **analyte-scoped** decision — a laboratory may
be entirely comfortable autoverifying sodium and entirely uncomfortable
autoverifying troponin, and that is a clinical judgement, not a system setting.

### 2. Quality control is in control

The same check a human release passes. No QC in the last 24 hours, or a failed
run, and nothing is released.

### 3. The result is numeric and inside its reference interval

Using the **patient's demographic interval** where one exists, not the
catalogue default. "Normal" means the same thing on a neonate as on an adult,
which is the only way this is safe.

If no reference interval is defined at all, nothing is released — "normal" has
no meaning without one.

### 4. It is not a critical value

Never, under any configuration. A panic result must reach a person who
telephones the requesting clinician and documents read-back (CAP GEN.41320).
There is no acceptable automatic substitute for that, and there is no setting
that permits one.

### 5. A delta check did not flag it

A large change from the patient's own previous value is precisely the signal a
rule cannot interpret. Somebody looks.

### 6. It carries no flags and no hold

Any flag at all — including one a rule itself added — blocks release.

### 7. The specimen was received as acceptable

Marginal or rejected at reception is a human decision.

### 8. The order has no open exception

Something about that order is already known to need attention.

### 9. The result has not been amended

It has already gone wrong once.

## Tutorial: switch it on for one analyte

### 1. Decide, and record the decision

Before touching the software: which analyte, on what evidence, agreed by whom.
Raise a change control record. This is a change to how results reach patients.

### 2. Permit the analyte

**Settings → Test definitions →** your test **→** tick *auto verify permitted*.

### 3. Write the rule

**Settings → Decision rules → New**, applying to that test, with a single
action: *Request automatic verification*.

You can add conditions to narrow it further — routine priority only, adults
only, manual entry excluded. You do not need to add conditions restating the
guardrails; they apply whether you write them or not.

### 4. Simulate

Against real orders, as in [approving a
rule](/help/rules-and-automation/approving-a-rule/).

### 5. Approve it

### 6. Watch the firing log for a week

**Settings → Rule firing log**, filtered to your rule. Look at what was
released and — more usefully — what was refused, and why.

## Reading a refusal

When a rule asks for automatic release and a guardrail says no, the firing log
entry lists **every** reason, not just the first:

> * `GLU is not approved for autoverification. Enable it on the test definition
>   once the laboratory has validated it.`
> * `Quality control: No quality control has been run for GLU in the last 24
>   hours.`
> * `The result is above the reference interval.`

All at once, deliberately. Fixing one blocker only to discover another on the
next run wastes days.

## What the report says

The signature manifest on a report released this way reads:

> Autoverified by rule: Routine chemistry release (v2) — no human review —
> 2026-09-15 14:30:07 UTC

A clinician reading it knows no human eye was involved. This matters. Recording
the scientist who happened to be logged in would be false attribution — a
graver Part 11 §11.50 finding than having no human signature at all.

The electronic signature record has a null signer and names the rule and its
version instead.

## Taking a result back

Any laboratory user can override an automatic verification.

1. **Settings → Rule firing log**
2. Open the entry
3. **Override the automatic release**, with a reason

The result returns to the worklist as *Resulted*, the order reopens, and the
override is audited. The original rule signature is **kept** — Part 11 records
are permanent, so it is superseded rather than removed. What a reader sees
afterwards is the whole history: the rule released it, a named person pulled it
back, and why.

This is also how you satisfy a patient's GDPR Article 22(3) right to human
review of an automated decision.

## Stopping everything at once

Set `RULES_ALLOW_AUTO_VERIFICATION=0` and restart. All automatic release stops
immediately across the installation, whatever any individual rule says. Use it
during a QC investigation, or whenever you want to stop without first working
out which rules are involved.

## An honest summary of the risk

Autoverification moves a decision from a person to a configuration. The
guardrails above make that safe for results that are unambiguously normal on an
analyte the laboratory has validated, backed by current quality control.

They do not make it safe to autoverify an analyte the laboratory has not
thought carefully about, and no amount of engineering will. The most important
control here is the first one, and it is a human one.
