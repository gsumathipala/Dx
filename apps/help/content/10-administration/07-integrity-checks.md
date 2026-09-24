---
title: Checking the system is self-consistent
summary: What `check_workflows` looks for, what each finding means, and when to run it.
audience: manager, medic
keywords: integrity, consistency, check, audit, inspection, upgrade, tutorial
---

## Two different questions

The test suite answers *does the software behave correctly?* It runs on every
change and it does not look at your data.

`check_workflows` answers a different question: **does the data in this
laboratory contradict itself right now?** Those come apart in normal use. A
reference interval edited after results went out, an order marked complete
while one analyte is still unverified, an analyte approved for autoverification
with no quality control target — none of those is a software bug, all of them
are wrong, and none appears on any screen.

## Running it

Ask your administrator to run:

```
python manage.py check_workflows
```

It prints findings grouped by severity and exits non-zero if any are errors, so
it can be wired into a nightly job.

**Run it after an upgrade, after any data migration, and before an
inspection.** The last one is the point: everything it reports is something an
assessor could find, and it is much better to find it first.

## What the severities mean

| | |
| --- | --- |
| **ERROR** | The data contradicts itself. Something has gone wrong and a person must look. |
| **WARN** | Consistent, but operationally wrong or heading that way. |
| **INFO** | Worth knowing. No action implied. |

## The findings you are most likely to see

### AUDIT-CHAIN / AUDIT-TRIGGERS

The audit trail does not verify, or its database-level protection is missing.
**Stop and investigate before anything else** — nothing else in the report can
be trusted until this is explained. See
[chain integrity](/help/security-and-audit/chain-integrity/).

### ORDER-COMPLETE-UNVERIFIED

A report went out while part of it had not been verified by anybody. Find out
whether it was distributed, and to whom.

### RESULT-UNATTRIBUTED

A verified result naming nobody. CLIA §493.1291(c) requires the report to
identify who released it; a result naming nobody cannot be defended.

### CRITICAL-OVERDUE / CRITICAL-NOT-RAISED

Either a critical value passed its escalation deadline without anybody
recording a telephone call, or a critically flagged result never raised a
notification at all — so nobody was ever prompted. The second usually means a
result was written by something that bypassed the clinical engine.

### RESULT-FLAGS-STALE

A result's stored flag disagrees with what the reference interval says today.
**This is expected after you edit an interval** — the stored flag is what was
reported at the time and is deliberately not rewritten. Worth confirming the
edit was intended, and whether anything released against the old interval needs
reviewing.

### AUTOVERIFY-NO-QC / AUTOVERIFY-NO-INTERVAL

An analyte is ticked for automatic release but has no quality control target,
or no reference interval. Nothing will ever be released for it — which is safe,
but the configuration is claiming something the system cannot honour. See
[autoverification](/help/rules-and-automation/autoverification/).

### RULE-UNAPPROVED

A rule is enabled but awaiting approval, so it is not firing. Somebody probably
believes it is running. Editing a rule withdraws its approval, which is almost
always the cause.

### INTERFACE-NO-CODEMAP

A bidirectional interface has no test code map, so
[host query](/help/integrations/host-query/) answers the analyser in Dx codes
it will not recognise. The analyser runs nothing, or the wrong thing.

### DOWNTIME-NO-PACK / DOWNTIME-PACK-STALE

No downtime pack exists, or the newest is more than twelve hours old. If the
system became unavailable now, the laboratory would have nothing to work from.
See [working when the system is down](/help/continuity/downtime/).

### CATALOGUE-INVERTED

A test's limits contradict each other — a reference low above its high, or a
critical limit inside the normal range. Every result will be flagged, or none
will, and neither is visible from the catalogue screen.

## If a finding is wrong

Tell somebody. A check that cries wolf gets switched off, and then the real
finding goes unseen — which is worse than not having the check at all.
