# Regulatory control mapping

This document maps each regulatory obligation Dx addresses to the mechanism
that enforces it and the code that implements it. It is written for a
laboratory quality manager preparing for inspection, and for a developer who
needs to know which behaviour is deliberate.

> **Scope.** Dx is laboratory software. Software alone does not make a
> laboratory compliant: accreditation also depends on personnel, premises,
> procedures and the laboratory's own validation of this system in its
> environment. The controls below are the parts a LIS can enforce.

---

## 1. Audit trail — 21 CFR Part 11 §11.10(e)

> *"Use of secure, computer-generated, time-stamped audit trails to
> independently record the date and time of operator entries and actions that
> create, modify, or delete electronic records."*

| Requirement | How Dx meets it | Where |
| --- | --- | --- |
| Computer-generated | Django model signals capture every create, update and delete across all applications; no developer action is needed to audit a new table | `apps/audit/signals.py` |
| Time-stamped | Both the event time and the time it reached the trail are recorded, so a delayed write is visible | `AuditEvent.timestamp`, `recorded_at` |
| Records old values | Field-level before/after diffs | `AuditEvent.changes` |
| Attributable | Acting user, role, IP address, user agent, session and request id | `apps/audit/context.py` |
| Secure / not modifiable | SHA-256 hash chain, plus PostgreSQL triggers refusing `UPDATE`, `DELETE` and `TRUNCATE` | `apps/audit/hashing.py`, `apps/audit/sql.py` |
| Retrievable | Filterable trail, per-record history, CSV export for inspectors | `apps/audit/views.py` |
| Retained | Audit retention class defaults to 10 years | `compliance.RetentionSchedule` |

**Tamper evidence.** Each event embeds the hash of its predecessor:

```
hash(n) = SHA256( canonical_payload(n) || hash(n-1) )
```

Altering or deleting any historic row invalidates every hash after it.
`manage.py verify_audit_chain` walks the chain and names the exact sequence
number at which it breaks. Verification runs on a schedule inside
`manage.py audit_worker`, writes a `ChainCheckpoint`, and raises an
`IntegrityAlert` on failure that cannot be cleared by acknowledgement alone.

**Durability.** The recorder is a persistent daemon thread. Events that must
not be lost — signatures, validation, release, authentication — are written
synchronously; everything else is queued. If the database is unreachable the
event is spooled to disk and replayed by the audit worker. The queue is never
silently dropped.

**The one gap, stated plainly.** Django does not emit model signals for
`bulk_create`, `bulk_update` or `QuerySet.update`, so a write made that way
produces no audit event. Nothing in the application takes those paths on
clinical data; the legacy importer is the only bulk writer and it records an
explicit summary event instead. Any future bulk write must do the same, or wrap
itself in `suppress_auditing()` so the omission is visible in the code rather
than accidental.

**Deliberate exceptions.** `TRUNCATE` protection blocks Django's test-database
teardown, so the test runner drops the triggers on the *test* database only
(`config/test_runner.py`); the tests that assert immutability reinstate them.
Restoring a production backup requires `apps.audit.protection.unprotected()`,
which logs the fact and reinstates protection afterwards.

---

## 2. Electronic signatures — 21 CFR Part 11 §11.50, §11.70, §11.200

| Requirement | How Dx meets it | Where |
| --- | --- | --- |
| Printed name, date/time, meaning | Captured at signing and printed on the report | `ElectronicSignature.manifest` |
| Signature linked to its record | SHA-256 of the signed content, plus the audit sequence number | `record_hash`, `audit_sequence` |
| Not transferable / re-authentication | Password re-entry required at signing | `compliance.services.apply_signature` |
| Signatures are permanent | Deletion refused in the ORM and by a database trigger | `ElectronicSignature.delete`, `apps/audit/sql.py` |

Configurable via `REQUIRE_REAUTH_FOR_SIGNATURE`. Disabling it is recorded on
the signature itself (`reauthenticated=False`), so a reviewer can see which
signatures were applied without re-verification.

---

## 3. Access control — 21 CFR Part 11 §11.10(d), §11.300

| Control | Setting | Default |
| --- | --- | --- |
| Unique named accounts (no shared logins) | — | enforced by model |
| Authentication required on every view | allow-list only | `apps/accounts/middleware.py` |
| Role-based authority checks | per view | `apps/common/views.RoleRequiredMixin` |
| Password ageing | `PASSWORD_EXPIRY_DAYS` | 90 days |
| Password reuse prevention | `PASSWORD_HISTORY_DEPTH` | last 5 |
| Account lockout | `ACCOUNT_LOCKOUT_THRESHOLD` / `_MINUTES` | 5 attempts / 30 min |
| Idle auto-logoff | `IDLE_TIMEOUT_MINUTES` | 20 minutes |
| Failed sign-in recorded | — | always |

---

## 4. Quality control — CLIA 42 CFR §493.1256

QC values are evaluated against the **Westgard multirules** (1-2s, 1-3s, 2-2s,
R-4s, 4-1s, 10x) in `apps/quality/models.evaluate_westgard`.

**QC lockout is enforced, not advisory.** `check_qc_status` blocks technical
validation and clinical verification when the most recent QC run for that test
failed, or when no QC has been run in the preceding 24 hours. A failing run
automatically opens a CAPA record — an undocumented QC failure is precisely
what an inspection looks for.

Controlled by `ENFORCE_QC_LOCKOUT`.

---

## 5. Personnel competency — CLIA 42 CFR §493.1451(b)(8)

Staff may not technically validate or clinically verify results for a test they
are not currently assessed as competent to perform. Competency may be recorded
per test or per discipline; an expired record stops satisfying the gate on its
expiry date rather than when someone remembers to edit it
(`UserCompetency.effective_status`).

Controlled by `ENFORCE_COMPETENCY_GATING`. Administrators bypass the gate.

---

## 6. Independent result review — CLIA 42 CFR §493.1495

The analyst who entered a result cannot also verify it
(`check_self_verification`). Controlled by
`ENFORCE_SELF_VERIFICATION_BLOCK`.

---

## 7. Critical values — CAP GEN.41320

A result outside the panic limits raises a `CriticalValueNotification` with an
escalation deadline (30 minutes for STAT, 60 otherwise). Closing it requires
recording **who was notified, by what method, and that they read the result
back**. Demographic-specific critical limits take precedence over the test
default, so a paediatric panic value is not judged against an adult limit.

---

## 8. Proficiency testing — CLIA 42 CFR §493.801

PT surveys are tracked with their due dates, and a survey cannot be recorded as
submitted without the attestation that no inter-laboratory communication took
place (§493.801(b)(4)). An unacceptable graded result is flagged until a
corrective action is linked to it.

---

## 9. Method validation — CLIA 42 CFR §493.1253(b)(1)

A method cannot be marked approved until accuracy, precision, reportable range
and reference interval are all recorded as verified. The form names whichever
elements are still outstanding.

---

## 10. Instrument maintenance — CLIA 42 CFR §493.1254

Equipment carries both service and calibration dates. An instrument past its
calibration date is flagged and reported on the compliance dashboard;
`Equipment.usable` is False for such an instrument.

---

## 11. Document control and training — ISO 15189:2022 §8.3

Controlled documents are versioned, require an effective date and a scheduled
review date before they can be made active, and record which staff have
acknowledged the current version. Documents past their review date appear on
the compliance dashboard.

---

## 12. Nonconformance and CAPA — ISO 15189:2022 §8.7

A CAPA cannot be closed until root cause, corrective action and effectiveness
check are all documented. QC and PT failures open one automatically.

---

## 13. Risk management — ISO 15189:2022 §8.5

Risks are scored (likelihood × severity) with a residual score after mitigation;
those rating High surface on the compliance dashboard.

---

## 14. Change control — 21 CFR Part 11 §11.10(a)

A change affecting result production cannot be recorded as implemented without
validation evidence.

---

## 15. Privacy — HIPAA Security & Privacy Rules

| Requirement | Mechanism | Where |
| --- | --- | --- |
| Audit controls, §164.312(b) | Every view of an identifiable patient record is logged | `PHIAccessLogMiddleware` |
| Accounting of disclosures, §164.528 | Disclosures outside treatment/payment/operations recorded for six years | `DisclosureAccounting` |
| Automatic logoff, §164.312(a)(2)(iii) | Idle session termination | `RegulatorySessionMiddleware` |
| Encryption, §164.312(a)(2)(iv) and (e)(2)(ii) | AES-256-GCM with scrypt for archives and exports | `apps/compliance/encryption.py` |
| Consent and withdrawal | Per-purpose consent records | `PatientConsent` |
| Emergency access ("break the glass") | Flagged on the access record | `PHIAccessLog.break_the_glass` |
| Minimum necessary, §164.502(b) | The installer role is barred from patient data entirely, and identifiers are redacted from the screens it *can* reach | `apps/accounts/phi_barrier.py`, `apps/audit/redaction.py` |
| Minimum necessary, §164.502(b) — machines | API clients are scoped per resource and verb, named to an accountable owner, and must state a purpose before a PHI scope can be granted | `apps/api/models.py` |
| Audit controls, §164.312(b) — machines | Every successful API read of patient data is recorded as a disclosure, naming the client and its organisation | `apps/api/auth.py` |
| Disclosure minimisation | Webhook payloads strip direct identifiers by default; a subscriber fetches detail over the logged API instead | `apps/api/webhooks.py` |

**Redaction, not concealment.** The installer needs the audit trail to confirm
the chain is intact and that changes are attributable, so clinical entries are
shown with their content removed rather than withheld: record type, actor,
time, action and hashes remain, values do not. Record keys are replaced by a
keyed digest, because Safe Harbor (§164.514(b)(2)(i)(R)) counts "any other
unique identifying number" as an identifier. Clinical records are excluded from
the trail's free-text search outright — redacting a result would still confirm
the patient exists.

PHI access is logged separately from the change audit trail because reads vastly
outnumber writes and are pruned on a different retention schedule.

---

## 16. Record retention — CLIA 42 CFR §493.1105

Seeded as data, not hard-coded, so a laboratory under a stricter local rule can
lengthen a period without a code change.

| Record class | Default | Basis |
| --- | --- | --- |
| Test requisitions, test records, QC, PT, instrument, personnel | 2 years | §493.1105(a)(1)–(7) |
| Immunohaematology | 5 years | §493.1105(a)(3) |
| Cytology slides | 5 years | §493.1105(a)(7)(i) |
| Pathology reports | 10 years | §493.1105(a)(2)(ii) |
| Audit trail | 10 years | 21 CFR Part 11 §11.10(e) |

---

## 17. Amended reports — CAP

A corrected report retains the original value, is marked as amended on the
printed report with the reason and a narrative, is electronically signed, and
records whether the requesting clinician was notified.

---

## 18. Notifiable conditions

Results linked to a notifiable condition raise a public health notification with
the statutory reporting window; overdue notifications are flagged. All matching
conditions are raised, not just the first.

---

## 19. Automatic verification — CLIA 42 CFR §493.1291, CLSI AUTO10-A

Results may be released without a person reading them, by a decision rule. This
is the highest-risk capability in the system and it is treated as one.

| Control | Mechanism |
| --- | --- |
| Analyte-scoped opt-in | `TestDefinition.auto_verify_permitted`, off by default |
| Quality control must be in control | `check_qc_status` — the same gate a human release passes |
| Result must be numeric and within its interval | Demographic interval where one exists, not the catalogue default |
| Never a critical value | A panic result must reach a person who telephones it (CAP GEN.41320) |
| Never a delta-flagged result | A large change from the patient's own previous value is what a rule cannot interpret |
| Never a flagged, held, or non-numeric result | |
| Never on a specimen received as other than acceptable | |
| Never on an order with an open exception | |
| Never on an amended result | It has already gone wrong once |
| Installation-wide off switch | `RULES_ALLOW_AUTO_VERIFICATION=0` stops all automatic release immediately |

Every refusal is recorded on the `RuleExecution`, all of them at once rather
than the first found, so a laboratory tuning a rule set sees every blocker in
one pass.

**Attribution.** The release carries an electronic signature whose signer is
the *rule*, at the version that fired — `ElectronicSignature.signer` is null
and `automated_rule` names it. The signature manifest printed on the report
reads "no human review", so a clinician knows. Recording the user who happened
to be in session would be false attribution, which is a graver §11.50 finding
than having no human signature.

**Reversibility.** Any laboratory user may override an automatic verification
with a recorded reason. The result returns to the worklist, the order reopens,
and the original signature is retained — Part 11 records are permanent, so it
is superseded rather than removed.

**Change control.** A rule is versioned. Editing one increments its version and
withdraws its approval, so a modified rule stops firing until somebody
competent signs it again. Approval is itself an electronic signature recording
what was reviewed. This is what CLIA §493.1253 and ISO 15189 §8.5 require of a
change to the examination process.

---

## 20. Decision rules — CLIA 42 CFR §493.1253, ISO 15189:2022 §8.5

Interpretive comments, result flags, reflex additions and exception raising are
configured as data, by the laboratory, rather than written in code.

* Conditions are ANDed within a group and ORed across groups — expressive
  enough for what laboratories actually ask for, and renderable as a form a
  biomedical scientist can read and check. A rule nobody can read is a rule
  nobody can validate.
* A rule can be simulated against a real historic result before approval,
  which is the difference between validating a rule and hoping.
* Every firing records the facts the rule saw, so "why does this report say
  that?" is answerable months later.
* Automatic comments are attributed inline (`[Rule name] …`), so a reader can
  tell an automatic note from a scientist's opinion.

---

## 21. Data subject rights — GDPR Chapter III

| Right | Handling |
| --- | --- |
| Access, Art. 15 | Full export: demographics, orders, results, disclosures, and a statement of the automated decision-making in use (Art. 15(1)(h)) |
| Rectification, Art. 16 | By amendment, never overwriting — the original stays visible, the correction is signed, recipients are notified (also satisfies Art. 19) |
| Erasure, Art. 17 | Assessed per record against the retention schedule; refused with a stated basis where Art. 17(3)(b) or (c) applies |
| Restriction, Art. 18 | Flagged and enforced; clinical care continues, as Art. 18(2) permits |
| Portability, Art. 20 | FHIR R4 Bundle — machine-readable in the sense Art. 20(1) means, and loadable by another system |
| Objection, Art. 21 | Recorded and assessed |
| Human review, Art. 22(3) | Any autoverified result can be pulled back for a person to verify |

**The refusals are the substance.** A system that deletes on request destroys
records the laboratory is legally required to keep, irreversibly. Erasure is
assessed order by order: anything past its retention period is erased, anything
inside it is refused with the specific period and authority named, which is
what Art. 12(4) requires. Identifiers are removed only when nothing clinical is
retained.

Erasure destroys the clinical content and keeps the record shell — accession
number, dates, the fact of erasure. A dangling reference would corrupt the
audit chain, and a trail that can be broken by a deletion request is not an
audit trail.

Identity is verified before anything is disclosed or destroyed (Art. 12(6)),
and the statutory clock runs from receipt, not from verification — a laboratory
cannot extend its own deadline by being slow to check who is asking. Exports
are AES-256-GCM encrypted; the passphrase is never stored beside the file.

---

## 22. Exception management — ISO 15189:2022 §8.7

Everything needing a person appears on one queue: rejected specimens,
unacknowledged critical values past their escalation deadline, breached
turnaround, failed quality control, silent instrument interfaces, refused
inbound messages, failing integrations, amended reports and overdue data
subject requests.

Items are deduplicated by a stable source key, so a sweep can run every minute
without flooding the queue, and a recurring fault appears as one item with a
high occurrence count rather than as noise. A problem that returns after being
closed reopens the same item.

Closing an item requires a resolution note and may raise a CAPA. The queue is
therefore also a record of what the laboratory actually dealt with, which is
what §8.7 asks for when it requires nonconformities to be managed rather than
merely noticed.

---

## 23. Business continuity — CLIA §493.1291, CAP GEN, ISO 15189 §8.7

A laboratory does not stop when the LIS does. Every accreditation body asks to
see the downtime procedure, in writing, tested.

| Control | Mechanism |
| --- | --- |
| A record of every outage | `DowntimeEvent`, including drills |
| Working without the system | A self-contained downtime pack: outstanding orders, recent verified results, unacknowledged criticals, reference and critical limits, requester contacts |
| Results produced on paper reach the record | Backloading, recording the performer and the time of production separately from the person keying it in |
| The report identifies who performed the examination (§493.1291(c)) | `Result.entered_by` carries the performer, the audit trail carries the typist |
| Nothing is waved through | Backloaded results arrive as *Resulted* and pass technical validation and clinical verification normally |
| Nothing is forgotten | An ended outage stays on the exception queue until reconciled |
| Safe recovery | Read-only mode: the application refuses every write while a restore runs |

The pack is deliberately **unencrypted by default**, which is the one place
this system departs from "everything leaving the database is encrypted". A pack
that needs this application to open it is useless when this application is what
is missing. The honest control is an encrypted volume the laboratory
physically holds.

---

## 24. Identity — 21 CFR Part 11 §11.300, HIPAA §164.312(d)

| Requirement | Mechanism |
| --- | --- |
| Unique identification (§11.300(a)) | One account per person; SSO matches on the provider's `sub`, the only claim guaranteed stable |
| Additional authentication factor | TOTP (RFC 6238), required by default for roles that can change who else has access |
| Loss management (§11.300(c)) | Single-use recovery codes, stored hashed, so regaining access never requires an administrator to switch the control off |
| Authority checks (§11.10(g)) | Roles are assigned locally from an explicit claim map with a refusing default; a directory group rename cannot grant clinical authority |

**The installer account never authenticates through SSO.** It is the
break-glass account for the case where the identity provider is what has
failed, and an account that depends on the thing it exists to recover from is
not a break-glass account.

A second factor is still required after SSO unless the provider asserts one was
performed (`amr`). "SSO is enabled" is not the same claim as "MFA was
performed".

---

## 25. Specimen identification — Joint Commission NPSG 01.01.01

Labels carry **two patient identifiers** (name, MRN and date of birth) plus the
accession number as text and Code 128 barcode. The accession number is not one
of the two: it identifies the specimen, not the person.

Nothing is truncated to fit. Reprinting is unrestricted and audited, because a
laboratory that cannot reprint will hand-write, and a hand-written tube is the
pre-analytical error the barcode exists to remove.

---

## What this system does *not* do

Stated plainly, because an overstated claim is worse than a gap:

* It is **not a validated medical device**. The laboratory must perform its own
  installation, operational and performance qualification.
* It does **not** provide electronic prescribing, billing claim submission, or
  a patient-facing portal.
* Blood bank / transfusion medicine (`21 CFR 606`, AABB) is **not** implemented;
  the retention class exists but the workflow does not.
* Digital pathology image management is out of scope, as is anatomic pathology
  **synoptic reporting** (CAP eCC), case sign-out workflow and consultations.
  Blocks and slides are tracked; a hospital AP department could not run on it.
* **Molecular and next-generation sequencing** are out of scope: no pipeline
  integration, no variant interpretation.
* **Point-of-care device management** is not implemented. `POCT1-A` appears as
  a protocol choice with nothing behind it.
* **Send-out and reference laboratory management** is not implemented.
* **Revenue cycle** stops at invoices: no 837/835 EDI, eligibility checking,
  medical necessity (LCD/NCD) or ABN generation.
* There is **no patient portal**, and no result-embargo handling for the 21st
  Century Cures Act information-blocking rules.
* **Accessibility has not been audited.** It very likely does not meet
  WCAG 2.1 AA.
* The interface is **English only**. `USE_I18N` is on; nothing is translated.
* It is **single-site**. There is no facility or tenant concept, no enterprise
  master patient index and no cross-site master file harmonisation. A network
  of laboratories would run separate instances.
* **High availability and disaster recovery are deployment concerns.** The
  application is stateless behind the database and can run several instances,
  but clustering, failover, replication and RPO/RTO targets are not configured
  here and no numbers are claimed.
* It does **not** hold a SNOMED CT or full ICD-10 licence. The ICD-10 table is
  a lookup populated by the laboratory, not a terminology server.
* Database-level encryption at rest is a **deployment** responsibility —
  filesystem encryption or PostgreSQL TDE. What the application encrypts is
  everything it writes outside the database: archives, backups and exports.
