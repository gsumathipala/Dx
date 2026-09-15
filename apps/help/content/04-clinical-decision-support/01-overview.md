---
title: What the decision engine does
summary: The checks that run automatically on every result, and what each is for.
audience: scientist, medic, manager
keywords: decision support, rules, engine, overview, flags
---

## Six checks, every result

The moment a numeric result is saved, six things happen without anyone asking:

| Check | Asks | Produces |
| --- | --- | --- |
| **Reference interval** | Is this normal for this patient? | A flag: High, Low, Critical |
| **Delta check** | Has this changed a lot since last time? | A flag for review |
| **Critical value** | Is this immediately dangerous? | A notification requiring a call |
| **Reflex rule** | Does this warrant a further test? | A test added to the order |
| **Calculated test** | Can something be derived from this? | A computed analyte |
| **Notifiable condition** | Must a public health body be told? | A statutory notification |

They are advisory, not decisive. Each flags something for a qualified person to
consider. None of them releases, withholds or interprets a result on its own.

## Why automate at all

A busy laboratory produces thousands of results a day. A human comparing each
against an interval, then against the patient's history, then against a list of
panic limits, will miss things — not from carelessness but from volume.

Automation catches the routine reliably so people can spend attention on what
is unusual. The failure mode to avoid is the opposite: automation that decides,
leaving nobody looking.

## Where the rules live

| Rule | Configured at |
| --- | --- |
| Reference intervals | Test definitions, and demographic reference intervals |
| Critical limits | Test definitions (`panicLow`, `panicHigh`), and demographic intervals |
| Delta checks | Settings → Delta check rules |
| Reflex tests | Settings → Reflex testing rules |
| Calculated tests | Settings → Calculated tests |
| Notifiable conditions | Settings → Notifiable conditions |

Changing any of these is a change to how results are interpreted. Each edit is
recorded in the audit trail, and significant changes should carry a
[change control record](/help/administration/change-control/).

## Rules do not run retrospectively

A new rule applies to results entered **after** it. Changing a critical limit
does not re-examine yesterday's results.

If a limit was wrong and results were released against it, that is a
nonconformance and possibly an
[amended report](/help/reporting/amended-reports/) — not something a
configuration change fixes by itself.
