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

**Quality** — Westgard multirule QC with Levey-Jennings charts, QC lockout,
instrument maintenance and calibration records, proficiency testing, method
validation, CAPA, risk register and change control.

**Audit** — an immutable, hash-chained event trail covering every change in the
system, enforced append-only at the database level. See
[docs/REGULATORY.md](docs/REGULATORY.md).

**Interoperability** — FHIR R4 (Patient, Observation, DiagnosticReport, Bundle),
HL7 v2 ORU^R01 export, LOINC catalogue, and a standalone instrument server
speaking ASTM E1381/E1394 and HL7 MLLP.

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
pre-production checklist are in **[INSTALL.md](INSTALL.md)**.

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

# and, to test it without an analyser:
python -m dx_instrument.simulator 2026-01-02-0001 --protocol astm
```

See [instrument_server/README.md](instrument_server/README.md).

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
  interop/           FHIR, HL7, LOINC, instrument ingest
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

Covers the audit chain and its immutability, the regulatory controls, the
clinical engine, accessioning under concurrency, the instrument protocols, and
a smoke test that renders every registered route.

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
| `INSTRUMENT_INGEST_TOKEN` | Shared secret for the instrument interface | — |
| `TRUST_PROXY_HEADERS` | Honour `X-Forwarded-For` (only behind a trusted proxy) | `False` |

The four enforcement switches exist because a laboratory in its commissioning
phase may need to run without them. Their state is shown on the compliance
dashboard, so nobody is misled about which controls are live.

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

## Licence

See [LICENSE](LICENSE).
