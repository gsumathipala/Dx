---
title: The installer account
summary: Separation of duties, what the installer can and cannot do, and why its password cannot be reset.
audience: administrator, manager
keywords: installer, separation of duties, phi barrier, permanent account, redaction
---

## Why it exists

Whoever installs and maintains a system normally acquires, as a side effect,
the ability to read everything in it. For a system holding patient records that
is a poor arrangement: it puts clinical confidentiality in the hands of someone
with no clinical role and no care relationship with any patient.

The installer role separates the two. It holds the **highest system authority**
and **no clinical authority at all**.

> HIPAA's minimum necessary standard (45 CFR §164.502(b)) says access should be
> limited to what a role requires. A person maintaining a server does not
> require patient names to do it.

## What it can do

- Add, edit, disable and delete accounts, and reset their passwords
- Manage departments
- Configure instrument interfaces and view instrument traffic
- Change system configuration and alerts
- View the audit trail and verify its integrity
- Record change control entries
- Run maintenance, including resetting the database

## What it cannot do

Patients, orders, results, reports, critical values, histopathology,
microbiology, billing, specimen tracking and the global search are **refused**.

Enforced on every request. An installer typing a patient URL directly is
refused identically to one clicking a link that is not there.

It also cannot configure the test catalogue, clinical rules, QC targets or
retention policies — those are the laboratory's clinical decisions.

## Identifiers are redacted, not merely hidden

The installer keeps the audit trail, because verifying it is part of the job.
Clinical entries appear **redacted**: record type, actor, time, action and chain
hashes are shown; names, MRNs, dates of birth and accession numbers are not.

Record keys are replaced by a short token, so an installer can see that several
entries concern the same record without being handed a key that addresses it.

Clinical records are excluded from the audit **search** entirely — a search for
an MRN that returned a hit would itself confirm the patient exists.

The same applies to the instrument message log, where a raw ASTM or HL7 payload
would otherwise contain the patient's name.

## Its two protections

**Its password cannot be reset by anyone else.** Not by an administrator, not
through any screen. An administrator who could reset it would simply *become*
the installer, and the separation would be decorative. Only the installer can
change it — or someone with shell access, using
`manage.py reset_installer_password`.

**It cannot be deleted.** A system with no installer cannot be recommissioned or
recovered.

## The control the laboratory keeps

**An administrator can disable it.**

That is the balance. The laboratory can always shut the installer out, and can
never take the account over. A disabled installer cannot sign in until an
administrator re-enables it.

## One account

There is exactly one, created during installation with
`manage.py create_installer`. The role is not offered when creating a user, so
a second cannot be made through the interface.
