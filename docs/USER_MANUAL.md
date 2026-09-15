# Dx user manual

How to use the system, by role and by task.

For installing it, see [INSTALL.md](../INSTALL.md). For which regulation each
control satisfies, see [REGULATORY.md](REGULATORY.md).

---

## Contents

1. [Signing in and your password](#1-signing-in-and-your-password)
2. [Finding your way around](#2-finding-your-way-around)
3. [Roles and what each can do](#3-roles-and-what-each-can-do)
4. [The installer account](#4-the-installer-account)
5. [Managing user accounts](#5-managing-user-accounts)
6. [The clinical workflow](#6-the-clinical-workflow)
7. [Critical values](#7-critical-values)
8. [Quality control](#8-quality-control)
9. [Reports and corrections](#9-reports-and-corrections)
10. [The audit trail](#10-the-audit-trail)
11. [Maintenance and resetting the system](#11-maintenance-and-resetting-the-system)
12. [When the system stops you](#12-when-the-system-stops-you)

---

## 1. Signing in and your password

Open the address your laboratory uses — by default `http://localhost:8000` —
and sign in with your own username. Accounts are personal and are never shared:
every result, signature and change is recorded against the person who made it.

### Changing your own password

**Anyone can change their own password at any time.** Use **My password** at the
bottom of the sidebar.

You will need your current password, and the new one must:

* be at least 8 characters,
* not be one of your last 5 passwords,
* not be a commonly used password, and
* not be entirely numeric.

### If you are asked to change it as soon as you sign in

Two things cause that:

* Your password has reached the end of its life (90 days by default).
* An administrator has issued you a **temporary** password.

Either way you cannot go anywhere else until you have set a new one. That is
deliberate — a temporary password is known to someone other than you.

### If you are locked out

Five failed attempts lock the account for 30 minutes. Wait, or ask an
administrator to reset your password. The lock is lifted by a reset.

### You will be signed out when idle

After 20 minutes of inactivity you are signed out automatically, so an
unattended screen does not leave your account open. Anything you had typed but
not saved is lost, so save before you walk away.

---

## 2. Finding your way around

### The search box

At the top of the sidebar. It takes an **accession number**, an **MRN** or a
**patient's surname**.

Typing or scanning an exact accession number takes you straight to that order,
opening it at whatever stage it has reached:

| The order is | You land on |
| --- | --- |
| Awaiting reception | Specimen receiving |
| Awaiting results or authorisation | Result entry |
| Released | The report |

Barcode scanners work with no setup — they type the barcode and press Enter.
Press **`/`** from anywhere to jump into the search box.

### The sidebar

The sidebar holds only what you use during a shift. Everything configured
occasionally lives behind **Settings**, which is a searchable index — type
`delta`, `calibration` or `retention` rather than scanning a list.

### The dashboard

Your dashboard is a worklist, not a report. It shows what needs you now:
critical values awaiting notification, STAT orders, and the queues you can
clear. Every row is clickable.

---

## 3. Roles and what each can do

| Role | Purpose |
| --- | --- |
| **Installer** | Commissions and maintains the system. **No access to patient or clinical data at all.** |
| **Administrator** | Everything clinical and administrative: users, configuration, all laboratory screens. |
| **Laboratory manager** | Laboratory configuration, compliance oversight, KPIs, verification. |
| **Biomedical scientist** | Result entry, technical validation, clinical verification, QC. |
| **Medical officer** | Clinical verification, critical value documentation, reports. |
| **Clerk** | Accessioning, specimen reception, phlebotomy scheduling, patient registration. |
| **Phlebotomist** | Phlebotomy rounds and collection. |

Roles are not a simple ladder. The installer has the **highest system
authority** and the **lowest clinical authority** — see below.

---

## 4. The installer account

The installer exists so that whoever installs and maintains the system does not
thereby gain access to patient records. This is ordinary separation of duties,
and it satisfies the HIPAA "minimum necessary" standard for technical staff who
have no care relationship with any patient.

### What the installer can do

* Add, edit, disable and delete user accounts, and reset their passwords
* Manage departments
* Configure instrument interfaces and view instrument traffic
* Change system configuration and system alerts
* View the audit trail and verify its integrity
* Record change control entries
* Run maintenance, including **resetting the database**

### What the installer cannot do

Patients, orders, results, reports, critical values, histopathology,
microbiology, billing, specimen tracking and the global search are **refused**.

This is enforced on every request, not by leaving links out of the menu — an
installer who types a patient URL directly is refused just the same.

**No identifiers leak through the screens it can reach.** The installer keeps
the audit trail, because verifying it is part of the job — but clinical entries
appear redacted: the record type, who acted, when, and the chain hashes are
shown; names, medical record numbers, dates of birth and accession numbers are
not. Record keys are replaced by a short token, so an installer can still see
that several entries concern the same record without being handed a key. The
same applies to the instrument message log, where a raw ASTM or HL7 payload
would otherwise contain the patient's name. Clinical records are excluded from
the audit search entirely: a search that found one would itself confirm the
patient exists.

The installer also cannot configure the test catalogue, clinical rules, QC
targets or retention policies. Those are the laboratory's clinical decisions,
not the maintainer's.

### Its two special protections

**Its password cannot be reset by anyone else.** Not by an administrator, not
through any screen. An administrator who could reset it would simply *become*
the installer, and the separation above would be meaningless. Only the installer
can change it — or someone with shell access to the server, using
`manage.py reset_installer_password`.

**It cannot be deleted.** A system with no installer cannot be recommissioned or
recovered.

### The control the laboratory keeps

**An administrator can disable the installer account.** That is the point of
balance: the laboratory can always shut the installer out, without ever being
able to take the account over. A disabled installer cannot sign in until an
administrator re-enables it.

There is exactly one installer account, created during installation with
`manage.py create_installer`. It cannot be created or duplicated through the
web interface.

---

## 5. Managing user accounts

Available to **administrators** and the **installer**, at Settings → Users.

### Adding someone

1. **Users → New user**
2. Fill in username, full name, role, department and email.
3. Save. The account has **no usable password** yet.
4. Use **Reset password** on the new account to give them a temporary one.

You cannot create another installer account here — the role is not offered.

### Resetting someone's password

1. Find the account and choose **Reset password**.
2. Enter a temporary password twice.
3. **Give a reason.** It is recorded in the audit trail — for example
   "forgotten password, identity confirmed in person".
4. Hand the temporary password to them by a channel you trust. Not by the email
   account you are restoring access to.

They must change it the moment they sign in, so **you never know their working
password**. That is what makes their electronic signature theirs.

The **Reset password** action does not appear on the installer account.

### Disabling someone temporarily

Use **Disable**. The account cannot sign in until re-enabled. Nothing they have
done is altered — their results, signatures and audit entries stay exactly as
they are.

Use this for leave, suspension, or anyone who has left. It works on **every**
account including the installer's.

You cannot disable your own account.

### Deleting someone

Use **Delete**. If the person has ever signed or authorised a record, deletion
is **refused and the account is disabled instead**, and you are told so. That is
not a limitation to work around: a signature has to keep naming a real person,
or the record it signed means nothing.

You cannot delete your own account, or the installer's.

### Everything here is recorded

Every reset, suspension, re-enablement and deletion is written to the audit
trail against *your* account, with the reason you gave. Use **History** on any
account to see everything that has happened to it.

---

## 6. The clinical workflow

### Accessioning

**Accessioning** — choose the patient, tick the tests, set the priority and name
the requesting clinician. The system allocates the accession number; you never
type one.

### Receiving

**Receiving** — record the specimen's arrival and condition. If you reject it,
you must record the reason, so the requester can be told what to recollect.

### Entering results

**Worklist** → open an order.

Each row shows the analyte, its units, the reference interval, and — importantly
— **the patient's previous value with an arrow showing the direction of
change**. Whether a sodium of 131 matters depends on what it was last time.

**Typing quickly:**

| Key | Does |
| --- | --- |
| **Enter** or **↓** | Next value |
| **↑** | Previous value |
| **Ctrl+Enter** | Save |

The first field is focused when the page opens, so a whole panel can be entered
without touching the mouse.

### Authorising results

Results are released in two stages:

1. **Technical validation** — the analytical run is sound.
2. **Clinical verification** — the result is fit to report. This completes the
   order and releases the report.

The screen offers **only the action the order is ready for**. Both stages ask
for your password: that is your electronic signature, and it is required every
time.

**You cannot verify a result you entered yourself.** A second qualified person
must do it. This is a CLIA requirement, not a preference.

### Verifying several orders at once

On the **Worklist**, orders ready for clinical verification have a checkbox.
Tick as many as you like, enter your password once, and choose **Verify
selected**.

One signing covers the batch, and the signature records exactly which orders it
covered. Each order is still checked individually against your competency, the
QC status and the self-verification rule — if one is refused, you are told which
and why, and the others still go through.

---

## 7. Critical values

A result outside the panic limits raises a notification immediately. It appears
on your dashboard and under **Critical Values**.

To close one, choose **Document** and record:

* **who** you notified,
* **how** (telephone, in person, fax, secure message), and
* that they **read the result back to you**.

Read-back is required. It is the only thing that shows the value was received
correctly rather than merely sent.

STAT orders escalate after 30 minutes, others after 60. Overdue notifications
are shown in red.

---

## 8. Quality control

**Quality Control** — choose the control and enter the measured value. The
system applies the Westgard multirules (1-2s, 1-3s, 2-2s, R-4s, 4-1s, 10x) and
plots a Levey-Jennings chart.

* **Pass** — carry on.
* **Warning** (1-2s) — review before reporting.
* **Fail** — patient results for that test are **blocked from release** until
  acceptable QC is recorded, and a nonconformance is opened automatically for
  you to complete.

A test with no QC in the last 24 hours is also blocked. This is not something to
work around: releasing patient results on failed or absent QC is precisely what
an inspection looks for.

---

## 9. Reports and corrections

**Reports** lists released reports. Open one to view, print, or export it as
FHIR or HL7. The report carries its signature manifest: who authorised it, when,
and in what capacity.

### Correcting a released report

Open the report and choose **Amend**. You will be asked for the corrected value,
a reason, an explanation for the report, and whether the requesting clinician
has been told.

The system then:

* keeps the original value and shows it on the amended report,
* marks the report as amended,
* takes your electronic signature, and
* opens a nonconformance automatically — a report that went out wrong is a
  nonconformance by definition.

Use ordinary result entry for anything **not yet released**; amendment is only
for reports already in a clinician's hands.

---

## 10. The audit trail

**Audit Trail** shows every change made anywhere in the system: who, when, what
the value was before, and what it became. Filter by record type, action, user or
date, and open any record's **History** to see its whole life.

The trail cannot be edited or deleted by anyone, including administrators and
the database itself. Each entry is cryptographically linked to the one before
it, so altering or removing any historic entry is detectable.

**Chain Integrity** (managers and the installer) verifies the whole trail and
tells you the exact entry at which anything has been tampered with. Run it
whenever you like; it also runs on a schedule.

Managers can export the filtered trail as CSV for an inspector.

---

## 11. Maintenance and resetting the system

### Maintenance

**Maintenance** (administrators and the installer) shows audit health — whether
the recorder is running, whether the append-only protection is in place, and
when the chain was last verified — along with the commands for backup, chain
verification and restoration.

### Resetting the database

For commissioning a machine: install, load demonstration data, check everything
works, then erase it to hand over an empty system.

```bash
python manage.py reset_data --dry-run                       # see what would go
python manage.py reset_data --confirm "ERASE ALL DATA" --archive-to backups/
```

| Option | Effect |
| --- | --- |
| `--dry-run` | Report only; delete nothing |
| `--archive-to DIR` | Where to write the audit trail archive |
| `--keep-users` | Leave accounts, departments and competency records |
| `--keep-audit` | Erase data but leave the audit trail |
| `--i-understand-this-is-production` | Required when `DEBUG` is off |

**This is not recoverable from inside the application. Take a database backup
first.**

Before anything is deleted, the audit trail is **verified and written to a
file**. The new trail then opens with an entry recording the reset: who ran it,
when, how many entries the old trail held and the hash it ended on. An empty
audit table with no explanation would be indistinguishable from a cover-up, so
the system will not produce one — you can always reconcile the archive against
what the new trail says was there.

After a full reset there are no accounts. Create one before signing in:

```bash
python manage.py create_installer --username installer
```

---

## 12. When the system stops you

Refusals are deliberate and each has a reason. The message tells you which.

| Message | Why | What to do |
| --- | --- | --- |
| "You entered this result and cannot also verify it" | Independent review is required | Ask a second qualified colleague |
| "The most recent QC run failed" | Results are blocked until QC is acceptable | Investigate, repeat QC, complete the nonconformance |
| "No quality control has been run in the last 24 hours" | No current QC | Run QC for that test |
| "has no current competency record" | Competency lapsed or never assessed | Ask your manager to assess and record it |
| "Your password is required" | Every signature needs re-authentication | Enter your password |
| "This account is locked" | Five failed sign-ins | Wait 30 minutes or ask for a reset |
| "The installer role has no access to patient or clinical data" | Separation of duties | Ask a clinical colleague |
| "The installer account is permanent" | It cannot be deleted | Disable it instead |
| "cannot be reset from here" | The installer's password is self-service only | Use `manage.py reset_installer_password` on the server |
| "has signed or authorised records" | Signatures must keep naming a real person | The account is disabled instead — that is the intended outcome |

If a control is stopping work that you believe is correct, raise it with your
laboratory manager. The switches exist, they are visible on the compliance
dashboard, and turning one off is a decision with consequences — not a
workaround.
