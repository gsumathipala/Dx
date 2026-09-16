---
title: Working when the system is down
summary: The downtime pack, what to do on paper, and how results get back in afterwards.
audience: scientist, medic, manager, clerk, phlebotomist
keywords: downtime, outage, offline, paper, backload, contingency, tutorial, business continuity
---

## The laboratory does not stop

Blood keeps arriving and clinicians keep needing answers. Every accreditation
body asks the same question at inspection — *show me what you do when the LIS
is down* — and the answer has to be written, practised, and evidenced.

Three things have to work.

## 1. Knowing what was already requested

You cannot ask the system what is outstanding when the system is what is
missing. The **downtime pack** is a single file holding, as of the moment it
was written:

* every outstanding order — accession number, patient, MRN, date of birth,
  tests requested, priority, requester
* unacknowledged critical values
* each of those patients' recent verified results, so a number written by hand
  can still be compared with their own history
* every test's reference interval and critical limits
* requester telephone numbers

It is plain HTML with no stylesheet, no script, no images and no network. It
opens on any machine, from a USB stick, and prints on a ward printer.

**It is only as good as its age.** A pack from three weeks ago is worse than no
pack, because people trust it. It should be regenerated every fifteen minutes
by a scheduled job, and it must end up somewhere reachable when the server is
not — a laboratory workstation, or a stick somebody swaps.

Check **Settings → Downtime and continuity**: it shows when the last pack was
written and warns if that was more than twelve hours ago.

## 2. Producing results safely meanwhile

Work from the printed pack. Write results on the worksheet with the reference
and critical limits beside them.

**Critical values still have to be telephoned.** The system is not there to
remind you, so this is the thing most likely to be missed. Note the time, who
you spoke to, and the read-back — you will need all three when you document it
afterwards.

## 3. Getting them back in

### Tutorial: after the system returns

**Do not start typing yet.** Open **Settings → Backup and maintenance** and
confirm the audit chain verifies. If the outage involved a restore, entering
results into a database nobody has checked is how a laboratory ends up unable
to tell which results are real.

**Open the downtime record.** Settings → Downtime and continuity → the open
event → *Record as restored*, saying how it was fixed.

Recording the system as restored does **not** close the outage. It stays on the
[exception queue](/help/rules-and-automation/exception-queue/) until the paper
results are in.

**Enter each paper result.** *Enter paper results* on the downtime record.

| Field | What goes in it |
| --- | --- |
| Accession number | From the pack, or the tube |
| Who performed the test | **The person who ran it and wrote the number down** |
| When it was produced | The time on the worksheet, not now |
| Results | One per line, as `CODE = VALUE` — for example `K = 4.2` |

The *who* matters more than it looks. CLIA §493.1291(c) requires the report to
identify the person who performed the examination, and after an outage that is
rarely the person typing. Both are recorded: the result carries the performer's
name, and the audit trail carries yours.

The *when* matters too. The result is stored with the time it was produced, so
turnaround figures describe what happened to the patient rather than what
happened to the keyboard.

**Entered results are not verified.** They come in as *Resulted* and go through
technical validation and clinical verification exactly like anything else — by
someone competent, with QC in control. Nothing is waved through because it came
from paper.

**Document the critical values.** Anything you telephoned during the outage
needs its notification and read-back recording now.

**Reconcile.** Only when every paper result is in. That closes the outage and
clears the exception queue item.

## Read-only mode

Separate from downtime, and used during recovery: the application stays up and
reachable and **refuses every write**, showing everyone the reason.

Use it while a restore is running. A restore racing against live traffic is how
a laboratory ends up with an audit chain that will not verify.

Signing out still works — trapping people in a session they cannot leave
achieves nothing.

## Drills

Record a **drill** on the same screen. Running the procedure once a year, on a
quiet afternoon, with the pack you actually have, is the difference between a
documented procedure and a working one. It also produces exactly the evidence
an assessor asks for.

The most common thing a drill uncovers: nobody knows where the pack is.
