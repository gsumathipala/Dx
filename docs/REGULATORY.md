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
| Consent and withdrawal | Per-purpose consent records | `PatientConsent` |
| Emergency access ("break the glass") | Flagged on the access record | `PHIAccessLog.break_the_glass` |

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

## What this system does *not* do

Stated plainly, because an overstated claim is worse than a gap:

* It is **not a validated medical device**. The laboratory must perform its own
  installation, operational and performance qualification.
* It does **not** provide electronic prescribing, billing claim submission, or
  a patient-facing portal.
* Blood bank / transfusion medicine (`21 CFR 606`, AABB) is **not** implemented;
  the retention class exists but the workflow does not.
* Digital pathology image management is out of scope.
* The HL7 and FHIR interfaces cover result reporting; inbound order messages
  (ORM^O01) are not yet implemented.
