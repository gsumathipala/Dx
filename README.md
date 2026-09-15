# Dx — Clinical Laboratory Information System

A laboratory information system built on Django and PostgreSQL, covering the
full workflow from accessioning to authorised report, with the regulatory
controls a clinical laboratory is held to actually enforced rather than merely
recorded.

> **Research and evaluation use.** This is not a validated diagnostic system.
> A laboratory deploying it must perform its own qualification and validation.

---

## What it does

**Clinical workflow** — patient registry, accessioning with collision-safe
accession numbering, specimen reception and rejection, phlebotomy rounds,
result entry, two-stage authorisation (technical validation then clinical
verification), and printable reports carrying their signature manifest.

**Clinical decision engine** — delta checks against the patient's own history,
critical value detection with documented read-back, reflex testing, demographic
(age/sex/pregnancy) reference intervals, calculated analytes (LDL, anion gap,
eGFR CKD-EPI 2021, corrected calcium, osmolality, A:G ratio, transferrin
saturation), and notifiable condition surveillance.

**Rules engine** — laboratory-authored decision rules over the facts available
when a result is produced: value, flag, position against the patient's own
demographic reference interval, age, sex, specimen condition, previous result
and the change from it, QC status, ICD-10 indication. Actions append
interpretive comments, add flags, add follow-on tests, raise exceptions, notify
a role, or **autoverify**. Rules are versioned, simulated against real results
before approval, signed into service, and every firing records the facts it
saw.

**Autoverification with guardrails** — a rule may release a result without a
person reading it, but never a critical value, never a delta-flagged or
out-of-range result, never without in-control QC, and never on an analyte the
laboratory has not separately approved. The signature is attributable to the
*rule*, at the version that fired, and the report says "no human review". Any
laboratory user can override it with a recorded reason.

**Exception queue** — one screen for everything needing a person: rejected
specimens, unacknowledged criticals past escalation, breached turnaround,
failed QC, silent interfaces, refused inbound messages, failing integrations,
amended reports, overdue subject requests. Deduplicated by source key, closed
with a mandatory resolution note.

**Quality** — Westgard multirule QC with Levey-Jennings charts, QC lockout,
instrument maintenance and calibration records, proficiency testing, method
validation, CAPA, risk register and change control.

**Audit** — an immutable, hash-chained event trail covering every change in the
system, enforced append-only at the database level. See
[docs/REGULATORY.md](docs/REGULATORY.md).

**Interoperability** — FHIR R4 (Patient, Observation, DiagnosticReport,
Bundle); HL7 v2 `ORU^R01` outbound and `ORM^O01`/`OML^O21`/`ADT` inbound with
proper `AA`/`AE`/`AR` acknowledgement; **bidirectional instrument interfacing**
with host query (ASTM `Q`, HL7 `QBP^Q11`); LOINC and ICD-10 catalogues; and a
standalone instrument server speaking ASTM E1381/E1394 and HL7 MLLP.

**Public API and webhooks** — a versioned JSON API at `/api/v1/` with per-client
credentials, per-resource scopes, pagination and rate limiting; every PHI read
recorded as a disclosure. Signed, replay-resistant webhooks for order, result,
report, critical value, QC and exception events, with identifiers stripped by
default.

**Privacy rights** — GDPR subject access, rectification, erasure, restriction
and portability, with erasure assessed record by record against the retention
schedule and refused with a stated legal basis where CLIA requires retention.

**Also** — inventory with reagent consumption, in-house media manufacturing,
histopathology block/slide tracking, microbiology cultures and susceptibilities,
billing, specimen storage with chain of custody, worksheets, workstation
routing, TAT monitoring and KPIs.

---

## Getting started

### Requirements

* Python 3.11+
* PostgreSQL 14+

### Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit the database credentials
createdb dx

python manage.py migrate
python manage.py seed_demo    # optional demonstration dataset
python manage.py runserver
```

`seed_demo` creates a working laboratory — users with competency, a test
catalogue with reference and critical limits, acceptable QC, patients and
orders at each stage of the workflow. It prints the sign-in credentials, which
are also listed in [INSTALL.md](INSTALL.md#demonstration-sign-in-credentials).

Full setup instructions, the demonstration credentials, troubleshooting and a
pre-production checklist are in **[INSTALL.md](INSTALL.md)**. How to use the
system, by role and by task, is in **[docs/USER_MANUAL.md](docs/USER_MANUAL.md)**.
The API surface and the rules any new endpoint must follow are in
**[docs/API.md](docs/API.md)**.

A full help library — 76 topics covering every part of the system, with
tutorials and the laboratory practice behind each feature — is built into the
application at **Help** in the sidebar, or `/help/`.

### Running the audit worker

The web process records audit events in-thread. In production, also run the
supervised worker, which replays anything that could not be written and
re-verifies the hash chain on a schedule:

```bash
python manage.py audit_worker --verify-interval 3600
```

### Verifying the audit chain

```bash
python manage.py verify_audit_chain --checkpoint
```

Exits non-zero if the chain fails, so it can gate a nightly compliance job.

### Instrument interface

```bash
cd instrument_server
INSTRUMENT_INGEST_TOKEN=... python -m dx_instrument.cli --port 5150 --protocol astm

# bidirectional: also answer the analyser's work-list queries
INSTRUMENT_INGEST_TOKEN=... python -m dx_instrument.cli --port 5150 \
    --protocol astm --interface-id <id> --host-query

# and, to test it without an analyser:
python -m dx_instrument.simulator 2026-01-02-0001 --protocol astm
```

Host query is opt-in on both sides: the listener needs `--host-query` and the
`InstrumentInterface` record must be set to bidirectional. An analyser handed a
work list it was not configured to expect will run tests nobody ordered.

See [instrument_server/README.md](instrument_server/README.md).

### Background workers

```bash
# Deliver queued webhook events
python manage.py deliver_webhooks --forever --interval 15

# Raise exception queue items for conditions nobody reported
python manage.py sweep_exceptions --forever --interval 60
```

Both are idempotent and safe to run from cron instead, without `--forever`.

### Migrating from the Next.js version

```bash
python manage.py import_legacy --sqlite sqlite_v2.db --dry-run   # review first
python manage.py import_legacy --sqlite sqlite_v2.db
```

Records are reconciled on their business keys (test code, MRN, accession
number), not the legacy surrogate ids, so an import into a database that
already holds data does not create duplicates. Rows that cannot be converted
are **reported, not skipped silently**. Legacy bcrypt password hashes carry
across and keep working; any surviving cleartext password is imported as
unusable and must be reset.

---

## Layout

```
config/              Django project settings, URLs, test runner
apps/
  common/            Shared base models, constants, generic CRUD views
  audit/             Immutable hash-chained audit trail
  compliance/        Regulatory records and enforced controls
  accounts/          Users, departments, competency, record locks
  patients/          Patient registry and consolidated record
  laboratory/        Orders, specimens, results, accessioning, validation
  clinical/          Delta checks, critical values, reflex, reference intervals
  quality/           QC, Westgard rules, equipment, rejection criteria
  inventory/         Reagents, stock movements, manufacturing
  specialty/         Histopathology and microbiology
  operations/        Dashboard, KPIs, storage, custody, routing, settings
  billing/           Catalogue and invoicing
  reporting/         Reports, controlled documents, distribution
  interop/           FHIR, HL7 (in and out), LOINC, ICD-10, instrument ingest,
                     host query
  rules/             Decision rules, the evaluation engine, autoverification
  api/               Public JSON API, client credentials, webhooks
  help/              The in-application help library
instrument_server/   Standalone ASTM/HL7 TCP listener (stdlib only)
templates/           Django templates
tests/               Test suite
docs/                Regulatory mapping and reference material
```

---

## Tests

```bash
python manage.py test tests
```

412 tests. Covers the audit chain and its immutability, the regulatory
controls, the clinical engine, accessioning under concurrency, the instrument
protocols, inbound HL7 and host query, the API's authentication and scoping,
webhook signing and retry, the exception queue, GDPR erasure assessment, and a
smoke test that renders every registered route.

The autoverification tests are the ones to read first: each asserts that a
specific class of result — a critical value, a delta flag, an out-of-range
result, one without current QC — is **not** released.

---

## Configuration

Set in `.env`; see `.env.example` for the full list.

| Setting | Purpose | Default |
| --- | --- | --- |
| `ENFORCE_QC_LOCKOUT` | Block result release when QC has failed | `True` |
| `ENFORCE_COMPETENCY_GATING` | Require current competency to validate | `True` |
| `ENFORCE_SELF_VERIFICATION_BLOCK` | Entering analyst may not verify | `True` |
| `REQUIRE_REAUTH_FOR_SIGNATURE` | Password re-entry at signing | `True` |
| `PASSWORD_EXPIRY_DAYS` | Password ageing | `90` |
| `ACCOUNT_LOCKOUT_THRESHOLD` | Failed attempts before lockout | `5` |
| `IDLE_TIMEOUT_MINUTES` | Automatic sign-out | `20` |
| `RULES_ALLOW_AUTO_VERIFICATION` | Allow rules to release results without human review | `True` |
| `INSTRUMENT_INGEST_TOKEN` | Shared secret for the instrument interface, host query and inbound HL7 | — |
| `SUBJECT_REQUEST_EXPORT_DIR` | Where encrypted GDPR exports are written | `media/subject-requests` |
| `TRUST_PROXY_HEADERS` | Honour `X-Forwarded-For` (only behind a trusted proxy) | `False` |

The four enforcement switches exist because a laboratory in its commissioning
phase may need to run without them. Their state is shown on the compliance
dashboard, so nobody is misled about which controls are live.

`RULES_ALLOW_AUTO_VERIFICATION=0` stops all automatic release immediately,
whatever any individual rule says — for use during a QC investigation, or
whenever you want to stop without first working out which rules are involved.
It does not relax any other control; the per-analyte opt-in and every guardrail
still apply when it is on.

---

## Deployment notes

* Run `manage.py collectstatic` before serving; static files are served by
  WhiteNoise with a hashed manifest.
* Set `DJANGO_DEBUG=False` and a real `DJANGO_SECRET_KEY`.
* Serve over TLS. `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` and HSTS turn
  on automatically when `DEBUG` is off.
* Back up with `pg_dump`. Restoring requires the audit triggers to be dropped
  and reinstated — use `apps.audit.protection.unprotected()` and re-verify the
  chain immediately afterwards.
* Encryption at rest for the **database** is a deployment concern — filesystem
  encryption or PostgreSQL TDE. What the application encrypts is everything it
  writes outside the database: archives, backups and subject-access exports,
  with AES-256-GCM (`apps/compliance/encryption.py`).
* Run `deliver_webhooks` and `sweep_exceptions` under your process supervisor,
  or from cron. Without the first, webhook subscribers are never called;
  without the second, conditions nobody is present to notice never reach the
  exception queue.

## Licence

See [LICENSE](LICENSE).
