---
title: When the system stops you
summary: Every refusal message, what it means, and what to do about it.
audience: everyone
keywords: error, refused, blocked, forbidden, troubleshooting, control, message
---

## Refusals are deliberate

Almost everything that stops you is a control, not a fault. Each message says
which. The distinction matters: a control is working correctly and should not be
"fixed".

---

## Result entry and authorisation

### "You entered this result and cannot also verify it"

**Why:** CLIA requires independent review. The person who produced a result
cannot be the one who confirms it.

**Do:** ask a second qualified colleague to verify. You can still technically
validate your own work — it is *clinical verification* that needs another
person.

### "The most recent QC run for … failed"

**Why:** quality control says the method was not working, so results from it are
not trustworthy.

**Do:** investigate the failure, fix the cause, record an acceptable QC run. See
[QC lockout](/help/quality/qc-lockout/). Do not simply repeat the control hoping
for a pass.

### "No quality control has been run in the last 24 hours"

**Why:** no evidence the method is working. Absence of evidence is treated as
failed evidence.

**Do:** run and record QC for that test.

### "… has no current competency record for …"

**Why:** CLIA requires assessed competency before reporting results.

**Do:** ask your manager to assess and record competency. If you had one, it has
expired — records lapse on their expiry date automatically.

### "Your password is required to apply an electronic signature"

**Why:** a signature must prove it was you at that moment, not that you signed
in earlier.

**Do:** enter your password. If it is rejected, confirm you are signed in as
yourself.

### "Only a released report can be amended"

**Why:** amendment is for reports a clinician has already seen. An unreleased
result is simply corrected in result entry.

**Do:** go back to result entry and change the value.

### "The corrected value is the same as the current one"

**Why:** there is nothing to amend.

**Do:** check you selected the right analyte.

---

## Signing in

### "This account is locked"

**Why:** five failed attempts.

**Do:** wait 30 minutes, or ask an administrator to reset your password — a
reset clears the lock.

### "Your password must be changed before you continue"

**Why:** it has expired, or an administrator issued a temporary one.

**Do:** set a new password. You cannot go elsewhere until you do.

### You are signed out unexpectedly

**Why:** 20 minutes of inactivity.

**Do:** sign in again. Save work before leaving a workstation.

---

## The installer role

### "The installer role has no access to patient or clinical data"

**Why:** separation of duties. Whoever maintains the system does not thereby
gain access to patient records.

**Do:** ask a clinical colleague, or use an administrator account. This cannot
be granted to the installer.

### "The installer account is permanent"

**Why:** a system with no installer cannot be recovered or recommissioned.

**Do:** disable it instead, which has the same practical effect.

### "cannot be reset from here"

**Why:** an administrator who could reset the installer's password would hold
its authority.

**Do:** the installer changes their own password. For recovery, someone with
shell access runs `manage.py reset_installer_password`.

---

## Account administration

### "has signed or authorised records"

**Why:** a signature must keep naming a real person.

**Do:** nothing — the account was disabled instead, which is the intended
outcome.

### "You cannot disable your own account"

**Do:** ask another administrator, if you genuinely need it.

---

## Forms

### "A nonconformance cannot be closed until …"

**Why:** root cause, corrective action and effectiveness check are all required.
Closing without them records that something was fixed without saying what.

### "cannot be recorded as submitted without the attestation"

**Why:** CLIA requires attestation that no inter-laboratory communication took
place before a proficiency survey is submitted.

### "requires verification of accuracy, precision, reportable range and
reference interval"

**Why:** CLIA §493.1253 names all four before a method is approved. The message
says which are outstanding.

### "A batch cannot be released until its quality control has passed"

**Why:** in-house product is quarantined until checked.

### "The thresholds must read warning ≤ target ≤ breach"

**Why:** otherwise a warning would be raised after the target was already
missed.

---

## If something is genuinely broken

A control says *why* it stopped you. A fault does not — it produces an
unexpected error page, a blank screen, or a message that makes no sense in
context.

Report it through **Feedback**, with what you were doing and what you saw. If it
concerns a specimen, a result or a patient, raise a
[nonconformance](/help/quality/corrective-actions/) as well — feedback improves
the software; a nonconformance protects patients.
