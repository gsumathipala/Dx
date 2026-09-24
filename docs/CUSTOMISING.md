# Making it yours

How to take a fresh installation and turn it into *your* laboratory, in the
order you should do it.

Almost everything here is **configuration, not code** — done from screens, by a
manager or an administrator, with no deployment. Where something does need a
code change, this document says so plainly and says where.

Related: [INSTALL.md](../INSTALL.md) · [USER_MANUAL.md](USER_MANUAL.md) ·
[API.md](API.md) · [REGULATORY.md](REGULATORY.md)

---

## Contents

1. [Before you start](#1-before-you-start)
2. [Identity and accounts](#2-identity-and-accounts)
3. [The test catalogue](#3-the-test-catalogue)
4. [Reference intervals and critical limits](#4-reference-intervals-and-critical-limits)
5. [Decision rules and automatic verification](#5-decision-rules-and-automatic-verification)
6. [Quality control](#6-quality-control)
7. [Departments, benches and routing](#7-departments-benches-and-routing)
8. [Reports and who receives them](#8-reports-and-who-receives-them)
9. [Instruments and integrations](#9-instruments-and-integrations)
10. [Regulatory settings](#10-regulatory-settings)
11. [Branding and appearance](#11-branding-and-appearance)
12. [Things that need code](#12-things-that-need-code)
13. [Commissioning checklist](#13-commissioning-checklist)

---

## 1. Before you start

### Start from empty, not from the demonstration

The demonstration data exists to be looked at, not built on. Its accounts share
one publicly documented password, and leaving any of them in a live system is
an inspection finding on its own.

```bash
# If you seeded the demonstration and now want a clean start:
python manage.py reset_data --archive-dir ./archive --encrypt-archive
python manage.py create_installer --username installer
```

`reset_data` archives the audit trail before wiping, then opens a new chain
recording the previous chain's length and head hash — so a reset can be proved
not to have been a way of destroying evidence.

### Decide these three things first

They are awkward to change later:

| Decision | Why it is hard to reverse |
| --- | --- |
| **Your MRN format** | Every order, report and external message carries it |
| **Your test codes** | They appear on historic results, instrument code maps and any integration |
| **Time zone** (`DJANGO_TIME_ZONE`) | Stored data is UTC, but reported times shift |

### Work through it as the installer, then as a manager

The installer sets up the system; a manager sets up the laboratory. That split
is deliberate and it is worth following, because it is the split an inspection
expects to see.

---

## 2. Identity and accounts

### Roles

Seven, and they are **fixed in code** (`apps/common/constants.py`). You cannot
add an eighth from a screen — see [§12](#12-things-that-need-code).

| Role | For |
| --- | --- |
| Installer | Whoever maintains the system. No clinical access, ever |
| Administrator | User and system administration, plus full clinical access |
| Manager | Laboratory configuration, compliance, oversight |
| Scientist | Result entry, technical validation, clinical verification, QC |
| Medical officer | Clinical verification, critical values, reports |
| Clerk | Accessioning, reception, registration |
| Phlebotomist | Collection rounds |

### Adding your staff

**Settings → Users → New user.** The account starts with no usable password;
issue a temporary one, and the holder must change it at first sign-in.

### Connect your organisation's login (optional)

If you run Entra ID, Okta, Keycloak or anything else speaking OpenID Connect,
set the `OIDC_*` variables in `.env`. Map your directory groups onto Dx roles:

```
OIDC_ROLE_MAP={"Lab-Scientists": "scientist", "Lab-Managers": "manager"}
```

Anything unmapped is **refused, not guessed**. The installer account never uses
single sign-on — it is what you need when single sign-on is what has broken.

### Two-factor

On by default for administrators and installers (`MFA_REQUIRED_ROLES`). Widen
it to everybody if your policy says so.

---

## 3. The test catalogue

**Settings → Test definitions.** The single most consequential table in the
system: it decides what can be ordered, what a result means, and when somebody
is telephoned.

For each test:

| Field | Notes |
| --- | --- |
| **Code** | Yours, and permanent. Appears on labels, worklists and every interface |
| **Name** | What clinicians read |
| **Department** | Drives routing, worklists and competency |
| **Units** | Exactly as reported. No conversion happens anywhere |
| **LOINC code** | Needed for FHIR, HL7 and public health reporting |
| **Turnaround target** | Feeds the TAT thresholds |
| **Specimen types** | Which tubes are acceptable |
| **Auto verify permitted** | Leave **off** until you have validated it — see [§5](#5-decision-rules-and-automatic-verification) |

**Catalogue entries are deactivated, never deleted.** Historic results point at
them, and a report from 2026 must still resolve its analyte name in 2031.

### Loading a lot of them

There is no import screen. For a large catalogue, use the Django shell or write
a one-off data migration. Whatever you do, run `manage.py check_workflows`
afterwards — it catches inverted limits and missing intervals, which are
invisible on the catalogue screen.

---

## 4. Reference intervals and critical limits

Two layers, and the second wins.

**The catalogue default** is on the test definition itself:
`{min, max, panicLow, panicHigh}`. Any key may be absent, meaning *unbounded on
that side* — a tumour marker with only an upper limit is normal.

**Demographic intervals** (Settings → Demographic reference intervals) are
per age band, sex, and pregnancy. A single interval per analyte is wrong for
most of chemistry and haematology: creatinine in a six-year-old and
haemoglobin in a menstruating woman differ from the adult default by more than
the flag threshold, so a catalogue-only interval flags healthy children and
misses sick ones.

Several can match one patient; the **most specific** wins.

> **Critical limits must sit outside the reference interval.** A critical limit
> inside it means every normal result is also critical, and the system will do
> exactly as told. `check_workflows` reports this.

Editing an interval does **not** rewrite historic flags — the stored flag is
what was reported at the time. `check_workflows` reports the disagreement so
you can decide whether anything released against the old interval needs review.

---

## 5. Decision rules and automatic verification

**Settings → Decision rules.** This is where your laboratory's own knowledge
goes — the interpretive comments, suppression notes and reflex additions that
otherwise live in somebody's head.

Start by reading
[the help topic](../apps/help/content/13-rules-and-automation/01-why-rules.md),
then:

1. Write the rule as a draft.
2. **Simulate it against a real historic order** — condition by condition,
   nothing applied.
3. Have a manager approve it. Approval is an electronic signature.

**Editing an approved rule withdraws its approval**, so it stops firing until
somebody looks again. That is deliberate, and it is the most common cause of
"why did my rule not fire?".

### Turning on automatic verification

Do it **one analyte at a time**, and only after validating that analyte:

1. Raise a change control record. This changes how results reach patients.
2. Tick *auto verify permitted* on that test definition.
3. Write a rule whose action is *Request automatic verification*.
4. Simulate, approve, then watch the firing log for a week — particularly the
   refusals.

Nine guardrails apply whether or not you write them into the rule: in-control
QC, numeric, within the patient's demographic interval, never a critical value,
never delta-flagged, never otherwise flagged, never on a non-acceptable
specimen, never on an order with an open exception, never on an amended result.

`RULES_ALLOW_AUTO_VERIFICATION=0` stops all automatic release immediately,
across the installation, whatever any rule says.

---

## 6. Quality control

Order matters here, because each step depends on the last:

1. **QC materials** — the control and its lot. Targets are lot-specific.
2. **QC target values** — mean and SD per analyte per lot. Getting these wrong
   does not fail loudly: too large an SD passes everything, too small rejects
   every run until somebody disables the lockout.
3. **Run QC** before entering patient results. `ENFORCE_QC_LOCKOUT` blocks
   release when the most recent run failed, or when none exists in 24 hours.

**Rejection criteria** (Settings → Rejection criteria) are the reasons a
specimen may be refused at reception. Keep them as a list rather than free
text, so "how many haemolysed samples last month" stays a query.

---

## 7. Departments, benches and routing

**Departments** first — they drive worklists, competency and routing.

**Workstations** are benches, each declaring what it can do: which tests, which
specimen types, and its hourly throughput. A bench with no declared throughput
is treated as fully loaded, so routing sends work elsewhere.

**Routing rules** say which bench a test prefers, highest priority first.

**Turnaround thresholds** take three times, not one: target, warning and
breach. The warning tier is what makes a breach preventable rather than merely
recorded.

---

## 8. Reports and who receives them

**Requester registry** — clinicians, wards, clinics. This is both the
destination for reports *and* the contact for a critical value, which is why
the telephone number sits next to the delivery preference: at 3am those are the
same lookup.

**Distribution rules** — how each requester's reports are delivered: portal,
email, print, fax or HL7. A ward can have different routes for routine and
urgent work.

**Controlled documents** — your SOPs, under version control, with a record of
who has read them.

---

## 9. Instruments and integrations

### Analysers

**Settings → Instrument interfaces.** Create one per analyser, then run the
instrument server next to it:

```bash
dx-instrument-server --protocol astm --port 5150 \
  --interface-id <the interface id> --lis-url https://lis.example.org
```

The **test code map** translates the analyser's codes to yours. For a
bidirectional interface it is inverted to answer host queries, so an empty map
means the analyser is answered in codes it does not recognise — `check_workflows`
reports that.

### Orders from the hospital

Point your integration engine at `POST /api/middleware/hl7/`. It accepts
`ORM^O01`, `OML^O21` and `ADT`, and answers with a proper HL7 acknowledgement.

### Giving another system API access

**Settings → API clients.** Scope it to the least that will do the job. The
token is shown once.

---

## 10. Regulatory settings

In `.env`. Every one of these is **on** by default, and each exists because a
laboratory in commissioning may need it off briefly:

| Setting | What it enforces |
| --- | --- |
| `ENFORCE_QC_LOCKOUT` | No release while QC has failed or is missing |
| `ENFORCE_COMPETENCY_GATING` | No validation without current competency |
| `ENFORCE_SELF_VERIFICATION_BLOCK` | The person who entered a result may not verify it |
| `REQUIRE_REAUTH_FOR_SIGNATURE` | Password re-entry at every signature |
| `PASSWORD_EXPIRY_DAYS`, `ACCOUNT_LOCKOUT_THRESHOLD`, `IDLE_TIMEOUT_MINUTES` | Part 11 §11.300 |
| `RECORD_LOCK_TTL_SECONDS` | How long an open record stays reserved |

Their state is shown on the compliance dashboard, so nobody is misled about
which controls are live.

**Retention schedules** (Settings → Record retention) are seeded from the CLIA
minima and are data, not code — lengthen them if your jurisdiction is stricter.
They also drive what GDPR erasure may and may not remove.

---

## 11. Branding and appearance

Modest, and deliberately so — this is a clinical tool, not a product surface.

| What | Where |
| --- | --- |
| Colours, spacing, badges | `static/css/dx.css`, near the top (CSS custom properties) |
| Laboratory name on screen | `templates/partials/sidebar.html` and `templates/base.html` |
| Report header and footer | `templates/reporting/report_detail.html` |
| Specimen label layout | `apps/laboratory/labels.py` — ZPL and the printable sheet |

If you change the report or the label, check both against a real printer before
going live, and keep two patient identifiers on the label.

---

## 12. Things that need code

Honest list. Everything else on this page is a screen or a `.env` value.

| Change | Where | Difficulty |
| --- | --- | --- |
| A new **role** | `apps/common/constants.py`, plus every role tuple that should include it, plus the PHI barrier | Moderate — role checks are deliberately explicit, so nothing is missed |
| A new **calculated test** formula | `apps/clinical/services.compute_calculated_test` | Easy — each formula carries its own validity conditions, which is why it is code and not an expression |
| A new **rule condition subject** | `apps.rules.models.RuleCondition.Subject` and `engine.build_facts` | Easy |
| A new **exception source** | `apps.operations.models.ExceptionSource`, plus a sweep if it is a state rather than an event | Easy |
| A new **webhook event** | `apps.api.models.Webhook.Event`, plus an `emit` where it happens | Easy |
| **Report layout** beyond CSS | `templates/reporting/` | Easy |
| A new **API endpoint** | `apps/api/` — and read the rules in [API.md](API.md) first | Moderate; the rules are not optional |
| **Multi-site tenancy**, blood bank, anatomic pathology synoptic reporting | Not present. See [ROADMAP.md](ROADMAP.md) | Each is a project |

---

## 13. Commissioning checklist

Work down this in order. Everything here is something an assessor could ask
about.

- [ ] Demonstration data removed (`reset_data`), or never seeded
- [ ] Installer account created, its password held securely and not shared
- [ ] `DJANGO_SECRET_KEY` set to a real value; `DJANGO_DEBUG=False`
- [ ] TLS terminating in front of the application
- [ ] Shared cache configured if running more than one worker (`dx.W001`)
- [ ] `AUDIT_SPOOL_FILE` on durable storage (`dx.W002`)
- [ ] Departments, staff accounts and competency records entered
- [ ] Test catalogue loaded, with units and LOINC codes
- [ ] Reference intervals and critical limits entered and **checked for inversion**
- [ ] Demographic intervals entered for paediatric and sex-specific analytes
- [ ] QC materials, targets and a first passing run
- [ ] Requesters and distribution rules
- [ ] Instrument interfaces configured and exchanging messages
- [ ] Retention schedule reviewed against your jurisdiction
- [ ] Regulatory enforcement switches **all on**
- [ ] `manage.py downtime_pack` scheduled, writing somewhere reachable when the server is not
- [ ] `deliver_webhooks` and `sweep_exceptions` running
- [ ] Backups running, and a **restore tested**
- [ ] `manage.py check_workflows` clean
- [ ] `manage.py verify_audit_chain` clean
- [ ] Downtime procedure printed, and a drill run

> None of this makes the system validated. A laboratory deploying it must
> perform its own installation, operational and performance qualification —
> see [REGULATORY.md](REGULATORY.md).
