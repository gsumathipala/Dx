---
title: When a record is open by someone else
summary: Why records are reserved, how a reservation is released, and what to do when you need one somebody left open.
audience: scientist, medic, manager, clerk, phlebotomist
keywords: lock, locked, reserved, open by, concurrent, two users, tutorial
---

## What you will see

Open a patient record or a result-entry screen that a colleague already has
open, and you get a banner:

> **Open by jsmith.** This record is open by jsmith since 14:12. You can read
> it, but not change it, until they close it or the lock expires at 14:27.

You can read everything. The save buttons are replaced by a note saying who has
it.

## Why it works this way

The alternative — let both people type, then detect the collision when the
second one saves — is standard practice in most software and wrong here.

By the time the second scientist is told, they have entered forty analytes.
Something has to be discarded, and whichever way that goes, somebody has
re-keyed a set of patient results from memory at the end of a shift. That is
how transcription errors happen.

Reserving the record costs the second person a few minutes of waiting. Not
reserving it costs somebody a re-entered panel, and occasionally costs a
patient a wrong result.

## How a record is released

You do not have to do anything. A record is released when you:

* navigate away from the screen,
* save,
* sign out,
* or are signed out for inactivity.

It also **expires on its own** after fifteen minutes without contact from your
browser. While the screen is open your browser quietly refreshes the
reservation, so working slowly never loses it — the expiry only matters when a
browser closes without warning, a laptop sleeps, or the power goes.

## If you need a record somebody left open

Ask a manager, an administrator or the installer. **Settings → Record locks**
lists everything currently open, by whom, since when.

Breaking a lock requires a reason, and the reason goes into the audit trail
against that record. "User has gone off shift with the record open" is a good
reason. "Needed it" is not — after two people's edits collide, the first
question is who unlocked the record and why, and an unexplained override makes
that unanswerable.

## If your hold is broken while you are working

The page tells you:

> This record is now open by jsmith. Your changes will not be saved — reload
> before continuing.

**Reload before doing anything else.** Anything you typed after that message is
not going to be accepted, and typing on regardless only makes the loss larger.

## What is not locked

Only patient records and orders — the two places two people genuinely collide.
Configuration screens, the test catalogue, QC entry and the exception queue are
not reserved; concurrent edits there are rare and the last save winning is the
right outcome.

The lock is over *editing screens*. It is not a database-level guarantee and
does not try to be: the transactional integrity of a save is the database's
job. This stops two people being handed a form for the same record.
