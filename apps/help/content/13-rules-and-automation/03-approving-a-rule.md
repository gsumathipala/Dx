---
title: Approving and validating a rule
summary: Simulating a rule against real results, signing it into service, and why editing withdraws approval.
audience: scientist, manager
keywords: tutorial, approval, validation, simulate, version, change control, CLIA 493.1253
---

## A rule does not fire until it is approved

A new rule is a draft. An edited rule reverts to a draft. Only an approved
version of a rule is ever evaluated.

This is not bureaucracy. A rule decides what a report says. Changing one is a
change to the examination process, which CLIA §493.1253 and ISO 15189 §8.5 both
require to be validated and authorised. A rule that kept running on last year's
sign-off after being edited would make that requirement meaningless.

## Tutorial: validate before approving

### 1. Find a real case

You need an order whose results should make the rule fire, and ideally one that
should not.

For the haemolysis rule from the previous topic: find a recent order with a
raised potassium on a specimen marked marginal at reception.

### 2. Simulate

Open the rule. Scroll to **Try it against a real order**, enter the accession
number, and press *Simulate*.

You get a table, condition by condition:

| Condition | Group | Fact | Holds |
| --- | --- | --- | --- |
| Result — numeric value is greater than 5.5 | 0 | `6.4` | yes |
| Specimen — condition at reception is Marginal | 0 | `Marginal` | yes |

…and whether the rule matched overall.

**Nothing is applied.** It is a dry run. No comment is added, no flag set, no
result released.

### 3. Try the negative case

Now simulate against an order that should *not* match — a normal potassium, or
a raised one on an acceptable specimen. Confirm it does not match, and that the
fact values shown are what you expected.

This step catches the two most common mistakes: a threshold in the wrong units,
and a text value that does not match because the actual stored value is
`Marginal` and the rule says `marginal` with different spacing.

### 4. Approve

Fill in **what was reviewed**. This is the record an inspector reads, so write
what you actually did:

> Simulated against accessions 2026-09-14-0031 (haemolysed K 6.4 — matched) and
> 2026-09-14-0045 (acceptable specimen, K 6.1 — did not match). Reviewed by
> A. Patel, Consultant Chemical Pathologist, 15 September 2026. Wording agreed
> with the biochemistry duty rota.

Enter your password. Approval is an electronic signature under 21 CFR Part 11
§11.200 — it needs one component applied at the moment of signing.

The rule is now live at that version.

## Versions

| What you do | What happens |
| --- | --- |
| Save a new rule | Version 1, draft |
| Approve it | Version 1, live |
| Edit anything about it | Version 2, draft — **it stops firing** |
| Approve again | Version 2, live |

The rule's page shows its status plainly: *Live (v2)*, or *Draft v3 — awaiting
approval*.

Every firing records the version that fired, so a comment on a report from
March can be traced to exactly the rule text in force in March, not to what the
rule says today.

## Linking to change control

The rule form has a **change control** field. Link the rule to a change control
record when the change is significant enough to warrant one — a new
autoverification rule always is. It gives you one place showing the change, its
justification, its validation and its approval.

## Disabling versus editing

**Untick *active*** to stop a rule immediately without changing it. The version
and approval are preserved, so re-enabling does not require re-approval.

**Edit** it when the rule itself is wrong. That withdraws approval, which is
correct.

Use *disable* for "not right now" and *edit* for "not right".
