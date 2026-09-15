# Installing Dx

Step-by-step setup for a development or evaluation instance, including the
demonstration sign-in credentials.

For what the system does, see [README.md](README.md). For the regulatory
controls and how they are enforced, see [docs/REGULATORY.md](docs/REGULATORY.md).

---

## 1. Requirements

| | |
| --- | --- |
| Python | 3.11 or newer |
| PostgreSQL | 14 or newer |
| Disk | ~200 MB for the application and a small database |

No Node.js, npm or build step is required — the interface is server-rendered
Django templates with a single hand-written stylesheet.

---

## 2. Install

```bash
git clone https://github.com/gsumathipala/Dx.git
cd Dx

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

---

## 3. Configure

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```ini
DJANGO_SECRET_KEY=<a long random string>
POSTGRES_DB=dx
POSTGRES_USER=dx
POSTGRES_PASSWORD=<your password>
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## 4. Create the database

```bash
createdb dx
createuser dx --pwprompt        # if the role does not exist yet
```

Then apply the schema:

```bash
python manage.py migrate
```

This also installs the PostgreSQL triggers that make the audit trail
append-only. If the migration reports anything other than `OK`, stop and
resolve it before continuing — the audit controls depend on it.

---

## 5. Load the demonstration data (optional)

```bash
python manage.py seed_demo
```

This creates a working laboratory you can explore immediately: staff accounts
with competency records, a test catalogue with reference and critical limits,
acceptable quality control, patients, and orders sitting at each stage of the
workflow.

To rebuild it from scratch later:

```bash
python manage.py seed_demo --reset
```

---

## 6. Run

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000**.

---

## Demonstration sign-in credentials

> **These accounts exist only after running `seed_demo`, and only for
> evaluation.** They use a single shared, publicly documented password. Delete
> or disable every one of them before the system holds real patient data —
> shared and default credentials defeat the unique-account requirement in
> 21 CFR Part 11 §11.10(d) and would be an inspection finding.

**Password for all demonstration accounts:** `Dx-Demo-Pass!2026`

| Username | Name | Role | What this account can reach |
| --- | --- | --- | --- |
| `admin` | System Administrator | Administrator | Everything: user management, departments, notifiable conditions, audit trail, PHI access log, disclosure accounting, backup and maintenance |
| `lmanager` | Laboratory Manager | Manager | Compliance dashboard, all configuration, KPIs, epidemiology reporting, chain-integrity verification |
| `bscientist` | Senior Biomedical Scientist | Scientist | Result entry, technical validation and clinical verification, QC entry, worksheets |
| `jtech` | Junior Technologist | Scientist | Result entry and QC. Cannot verify a result they entered themselves |
| `dmedic` | Duty Medical Officer | Medical officer | Clinical verification, critical value documentation, reports |
| `rclerk` | Reception Clerk | Clerk | Accessioning, specimen reception, phlebotomy scheduling, patient registration |
| `pphleb` | Phlebotomist | Phlebotomist | Phlebotomy rounds and collection |

### Creating real accounts instead

For anything beyond evaluation, do not seed the demonstration data. Create the
installer account, sign in as it, and add your staff from **Settings → Users**:

```bash
python manage.py create_installer --username installer
```

The installer holds the highest **system** authority — user administration,
configuration, instrument interfaces, maintenance and the database reset — and
**no clinical authority at all**. It cannot open a patient, an order, a result
or a report, and that is enforced on every request rather than by hiding menu
entries.

Two protections follow from that separation:

* **Its password cannot be reset by an administrator.** Someone who could reset
  it would simply hold its authority. Only the installer can change it, or
  someone with shell access using `manage.py reset_installer_password`.
* **It cannot be deleted.** A system with no installer cannot be recommissioned.

The balancing control is that **an administrator can disable it**, so the
laboratory can always shut the installer out without being able to become it.

`createsuperuser` still exists, but produces a Django superuser with
unrestricted access and no PHI barrier. Prefer `create_installer`.

---

## What to try first

The demonstration data is arranged so the enforced controls are visible rather
than theoretical:

| Try this | What you should see |
| --- | --- |
| Sign in as `bscientist` → **QC & Calibration**, enter a wildly out-of-range control value | The run fails the Westgard rules, a nonconformance is opened automatically, and results for that test are blocked from release until acceptable QC is recorded |
| As `jtech`, enter a result, then try to clinically verify it yourself | Refused — the analyst who entered a result cannot verify it (CLIA §493.1495) |
| Clinically verify any result | Your password is requested again before the electronic signature is applied (21 CFR Part 11 §11.200) |
| **Critical Values** in the sidebar | A potassium of 6.9 awaiting clinician notification, with the read-back form required to close it |
| **Audit Trail** → open any event | Field-level before/after values, the acting user, and the event's position in the hash chain |
| **Chain Integrity** → *Verify chain now* | The whole trail is recomputed and confirmed intact |

---

## Running the supporting services

### Audit worker

The web process records audit events on a background thread. In any deployment
that matters, also run the supervised worker: it replays events that could not
be written and re-verifies the hash chain on a schedule.

```bash
python manage.py audit_worker --verify-interval 3600
```

### Verifying the audit chain on demand

```bash
python manage.py verify_audit_chain --checkpoint
```

Exits non-zero if the chain fails verification, so it can gate a nightly job.

### Instrument interface

```bash
cd instrument_server
INSTRUMENT_INGEST_TOKEN=<same value as in .env> \
  python -m dx_instrument.cli --port 5150 --protocol astm
```

To exercise it without an analyser, in another terminal:

```bash
python -m dx_instrument.simulator <accession-number> --protocol astm
```

See [instrument_server/README.md](instrument_server/README.md).

---

## Running with Docker instead

```bash
cp .env.example .env     # set DJANGO_SECRET_KEY and INSTRUMENT_INGEST_TOKEN
docker compose up --build
```

This starts PostgreSQL, the web application, the audit worker and the
instrument listener. Then seed the demonstration data if you want it:

```bash
docker compose exec web python manage.py seed_demo
```

---

## Commissioning a machine, then handing it over

Install, load the demonstration data, check the system behaves, then erase
everything so the laboratory starts clean:

```bash
python manage.py reset_data --dry-run                        # review first
python manage.py reset_data --confirm "ERASE ALL DATA" --archive-to backups/
python manage.py create_installer --username installer
```

| Option | Effect |
| --- | --- |
| `--dry-run` | Report what would be deleted; delete nothing |
| `--archive-to DIR` | Where to write the audit trail archive |
| `--keep-users` | Leave accounts, departments and competency records |
| `--keep-audit` | Erase operational data but keep the audit trail |
| `--i-understand-this-is-production` | Required when `DEBUG` is off |

> **This is not recoverable from inside the application.** Take a database
> backup first.

The reset cannot be silent. Before anything is deleted the audit trail is
verified and written to a file, and the new trail opens with an entry recording
who ran the reset, how many entries the previous trail held and the hash it
ended on. An unexplained empty audit table would be indistinguishable from a
cover-up, so the system will not produce one.

---

## Migrating from the Next.js version

If you are upgrading an existing Dx installation:

```bash
python manage.py import_legacy --sqlite sqlite_v2.db --dry-run   # review first
python manage.py import_legacy --sqlite sqlite_v2.db
```

The dry run reports exactly what would be imported and lists any row it cannot
convert. Records are matched on their business keys (test code, MRN, accession
number), not the old surrogate ids, so importing into a database that already
holds data will not create duplicates.

Existing bcrypt password hashes carry across and keep working. Any account
still holding a cleartext password is imported **without a usable password**
and must be reset before that user can sign in.

Legacy credentials are applied **only to accounts the import creates**. If a
username already exists in the target database, its password is left untouched
and the import reports it — so importing into a live system cannot replace a
working password with an older one.

> Run the import against a copy of your database first. `--dry-run` reports
> everything it would do without writing, including every row it cannot
> convert.

---

## Verify the installation

```bash
python manage.py test tests
```

129 tests covering the audit chain and its immutability, the regulatory
controls, the clinical decision engine, accessioning under concurrency, the
instrument protocols, and every registered page.

---

## Troubleshooting

**`connection to server on socket "/tmp/.s.PGSQL.5432" failed`**
PostgreSQL is not running. Start it however your installation expects — for a
system package that is usually `sudo systemctl start postgresql`; for a local
data directory it is:

```bash
pg_ctl -D <your data directory> -l <your data directory>/server.log start
```

**`Missing staticfiles manifest entry for 'css/dx.css'`**
You are running with `DJANGO_DEBUG=False` without having collected static
files. Run `python manage.py collectstatic`.

**`django.db.utils.ProgrammingError: relation "audit_events" does not exist`**
Migrations have not been applied. Run `python manage.py migrate`.

**`audit_events is append-only: TRUNCATE is not permitted on this table`**
This is the audit protection working as intended. Restoring a backup requires
lifting it deliberately with `apps.audit.protection.unprotected()`, and the
chain should be re-verified immediately afterwards.

**A demonstration account stopped accepting its password**
Something has changed that account — most often a `import_legacy` run against
the same database. Reset it:

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='admin')
u.set_password('Dx-Demo-Pass!2026'); u.save()
from apps.compliance.services import record_password_change, security_state
record_password_change(u)
s = security_state(u); s.failed_attempts = 0; s.locked_until = None; s.save()
"
```

Or rebuild the whole demonstration dataset with `python manage.py seed_demo --reset`.

**The installer cannot open a patient, order or report**
That is the design, not a fault. The installer maintains the system and has no
clinical access. Ask a clinical user, or use an administrator account.

**Nobody can sign in after a full reset**
A full reset removes every account. Create one:
`python manage.py create_installer --username installer`

**The installer's password is lost**
It cannot be reset from the web interface by design. On the server:
`python manage.py reset_installer_password`

**Sign-in says the account is locked**
Five failed attempts locks an account for 30 minutes. Adjust with
`ACCOUNT_LOCKOUT_THRESHOLD` and `ACCOUNT_LOCKOUT_MINUTES` in `.env`, or clear
it from the Django shell:

```python
from apps.compliance.services import security_state
state = security_state(user); state.failed_attempts = 0; state.locked_until = None; state.save()
```

---

## Before using this with real patient data

- [ ] Delete or disable every demonstration account listed above
- [ ] Set `DJANGO_DEBUG=False` and a unique `DJANGO_SECRET_KEY`
- [ ] Serve over TLS (secure cookies and HSTS enable automatically when `DEBUG` is off)
- [ ] Set `DJANGO_ALLOWED_HOSTS` to your real hostname
- [ ] Run `python manage.py check --deploy` and resolve every warning
- [ ] Configure database backups, and rehearse a restore including the audit-trigger step
- [ ] Run the audit worker under a process supervisor
- [ ] Confirm the enforced controls are on — the compliance dashboard shows their state
- [ ] Complete your own installation, operational and performance qualification.
      Dx is not a validated diagnostic device; validation in your environment is
      the laboratory's responsibility.
