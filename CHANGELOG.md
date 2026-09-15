# Changelog

All notable changes to the Dx Clinical LIS project will be documented in this file.

## [v3.1.0] - 2026-09-16
### Decision rules, autoverification, integrations and privacy rights

This release closes the gaps identified against the product requirements: the
rules engine, bidirectional instrument interfacing, a public API with webhooks,
ICD-10 and inbound HL7, the GDPR subject-rights workflow, and a unified
exception queue.

### Added

- **Rules engine** (`apps/rules/`). Laboratory-authored decision rules over
  twenty facts available at the moment a result is produced — value, flag,
  position against the patient's demographic reference interval, age, sex,
  specimen type and condition, previous result and the change from it, QC
  status, ICD-10 indication, entry source. Conditions are ANDed within a group
  and ORed across groups, deliberately renderable as a form a biomedical
  scientist can read and check. Actions append an attributed interpretive
  comment, add a flag, add a follow-on test, hold a result, raise an exception,
  notify a role, or request autoverification.
- **Rule change control.** Rules are versioned; editing one increments the
  version and withdraws its approval, so a modified rule stops firing until it
  is signed again. Approval is a Part 11 electronic signature recording what
  was reviewed. A rule can be simulated against a real historic order — every
  condition, the fact it saw, whether it held — without applying anything.
- **Autoverification, behind nine guardrails.** Per-analyte opt-in
  (`TestDefinition.auto_verify_permitted`, off by default), in-control QC,
  numeric and within the patient's demographic reference interval, never a
  critical value, never delta-flagged, never flagged or held, never on a
  specimen received as other than acceptable, never on an order with an open
  exception, never on an amended result. Every refusal is recorded — all of
  them, not just the first.
- **Rule-attributable signatures.** `ElectronicSignature.signer` is now
  nullable and `automated_rule` names the rule at the version that fired. A
  report released this way prints "no human review" in its signature manifest.
  Recording the user who happened to be in session would be false attribution.
- **Autoverification override.** Any laboratory user can return an
  autoverified result to the worklist with a recorded reason; the original
  signature is superseded, never removed. This also satisfies GDPR Art. 22(3).
- **Unified exception queue** (`operations.ExceptionItem`). Specimen
  rejections, unacknowledged criticals past escalation, TAT breaches, QC
  failures, silent interfaces, failed instrument messages, refused inbound HL7,
  failing webhooks, rule-raised items, amended reports and overdue subject
  requests. Deduplicated by source key; a recurrence bumps the count and a
  problem that returns reopens the same item. Closing requires a resolution
  note and can raise a CAPA. `manage.py sweep_exceptions` finds the conditions
  nobody is present to notice.
- **Host query — bidirectional instrument interfacing.** `HostQuery` plus
  `POST /api/middleware/query/`; the instrument server answers ASTM `Q` records
  and HL7 `QBP^Q11` with `--host-query`. Only outstanding tests on an open
  order are returned, in the analyser's own codes, and only for an interface
  configured bidirectional. Being asked about a specimen moves the order to
  *In Progress*.
- **Inbound HL7** (`apps/interop/inbound.py`, `POST /api/middleware/hl7/`).
  `ORM^O01` and `OML^O21` new orders and cancellations keyed on the placer
  order number, `ADT^A01/A04/A05/A08/A28/A31` patient registration and update,
  `ADT^A40` merge. Acknowledged with `AA`, `AE` or `AR` — kept distinct,
  because a sender that cannot tell wrong data from a broken message retries
  forever. Identity is the MRN and nothing else. A refused message raises an
  exception queue item.
- **ICD-10** (`interop.Icd10Code`, `laboratory.OrderDiagnosis`). Ranked
  diagnoses on an order, from `DG1` segments or the API, with code and
  description denormalised so a 2026 record still reads correctly after the
  catalogue row is revised.
- **Public JSON API** at `/api/v1/` (`apps/api/`). Per-client credentials
  (`<key id>.<secret>`, hashed at rest), nine per-resource scopes, pagination
  capped at 200, per-client rate limiting, optional IP allow-list and expiry.
  Catalogue, patients, orders, results, reports (JSON, FHIR or HL7), the
  exception queue and webhook subscriptions. Every successful PHI read is
  recorded as a disclosure naming the client and its organisation.
- **Webhooks.** Nine events, HMAC-SHA256 signed over a timestamp and the raw
  body, replay-resistant, HTTPS only, fired after commit, retried with backoff
  up to six attempts. Direct identifiers stripped by default. A subscriber
  failing twenty times running is disabled and raises an exception item.
  Delivered by `manage.py deliver_webhooks`.
- **GDPR subject rights** (`compliance.DataSubjectRequest`,
  `ProcessingRestriction`, `apps/compliance/subject_rights.py`). Access,
  rectification, erasure, restriction, portability, objection and human review.
  Erasure is assessed order by order against the retention schedule and refused
  with the specific period and authority named where Art. 17(3)(b) or (c)
  applies. Exports are AES-256-GCM encrypted; the Art. 15 document declares the
  automated decision-making in use, as Art. 15(1)(h) requires.
- **Twelve new help topics** across three new sections — rules and automation,
  integrations, privacy rights — taking the in-application library to 76
  topics, with tutorials for writing and approving a rule, switching on
  autoverification, working the exception queue, enabling host query, issuing
  an API credential, subscribing a webhook, and handling access and erasure
  requests.
- **176 new tests** (412 total), including one per autoverification guardrail.

### Changed

- `operations.Message.sender` is nullable, with `sender_label` for messages
  sent by a rule or the system. Attributing an automatic message to whoever
  happened to enter the result would be a small lie that becomes a large one
  during an investigation.
- `Order` gained `placer_order_number` and `source_message_id`; `Patient`
  gained `merged_into`/`merged_at`, so a merged record is retained rather than
  deleted — the audit trail refers to it.
- The PHI barrier now covers the `rules` and `api` namespaces, the host query
  log, the exception queue and data subject requests. Rule executions record
  the patient facts a rule saw.
- `rules.RuleExecution` and `api.WebhookDelivery` are excluded from automatic
  audit capture: both are already their own evidential record and both are
  high-volume. The rules that produce them are audited.
- `docs/API.md` documents the API that now exists, not only the rules for
  adding one. `docs/REGULATORY.md` gained sections 19–22 (autoverification,
  decision rules, data subject rights, exception management).

### Fixed

- The route smoke test treated token-authenticated API routes as broken
  session routes.

## [v3.0.0] - 2026-09-15
### ⭐ Major Release: Rewritten on Django and PostgreSQL

### Changed
- **Stack**: Replaced Next.js + Drizzle/SQLite with Django 5.2 + PostgreSQL. The
  React frontend is gone; every screen is a server-rendered Django template, so
  there is no Node.js dependency or build step.
- **Instrument server**: Reimplemented in Python (standard library only),
  speaking ASTM E1381/E1394 and HL7 v2 MLLP.

### Added
- **Immutable audit trail**: SHA-256 hash-chained events covering every change,
  enforced append-only by PostgreSQL triggers as well as the ORM, with a
  persistent recorder thread, disk spooling and scheduled chain verification.
- **Enforced regulatory controls**: 21 CFR Part 11 electronic signatures with
  re-authentication, CLIA competency gating, QC lockout, independent-review
  blocking, CAP critical value read-back, proficiency testing, method
  validation, CAPA, risk register, change control, HIPAA PHI access logging and
  disclosure accounting, and the CLIA record retention schedule.
  See `docs/REGULATORY.md`.
- **Interoperability**: FHIR R4 resources and HL7 v2 ORU^R01 export.
- **Migration path**: `manage.py import_legacy` moves the SQLite database
  across, reconciling on business keys and reporting rows it cannot convert.

### Fixed
- **Authentication bypass**: the `auth_session` cookie was an unsigned JSON user
  object that around 46 routes trusted for identity and role.
- **Duplicate accession numbers** under concurrent accessioning.
- **One-sided reference ranges** never produced a High/Low flag.
- **Delta checks** compared against later results and treated an unchanged
  value as a decrease.
- **Demographic reference intervals** were applied to patients of unknown age
  or sex.
- **Reagent consumption** matched by substring and could decrement the wrong
  item.
- **Silent write failures**: `writeDb` swallowed errors and reported success.
- **Date rendering** shifted dates, including dates of birth, by one day.

### Removed
- The Next.js application, Drizzle schema and migrations, and the TypeScript
  instrument server (recoverable from commit `c2ce325`).
- `docs/FEATURES.md` and `docs/USER_GUIDE.md`, which documented screens and API
  routes that no longer exist, and screenshots of the removed React interface.

## [v2.0.1] - 2025-12-27
### Fixed
- **Critical Data Persistence**: Fixed bug where `patients` and `testDefinitions` were not being saved to the database file.
- **Frontend Stability**: Refactored Patient Creation form to use `FormData` (uncontrolled components) to resolve React state race conditions.
- **API Real-time Updates**: Disabled Next.js aggressive caching on critical API routes (`patients`, `orders`, `users`) via `force-dynamic`.
- **User Management**: Fixed 404/silent failure when creating new users.
- **Accessioning**: Restored functionality for Patient Search and Order Creation.

## [v2.0.0] - 2025-12-19
### ⭐ Major Release: System Overhaul

### Added
- **SQLite Database**: Migrated from JSON file to SQLite with Drizzle ORM.
- **Secure Authentication**: Bcrypt password hashing, database-backed sessions.
- **Instrument Middleware**: Node.js TCP service for HL7/ASTM instrument integration.
- **Billing Module**: Automated invoice generation from orders.
- **Inventory Module**: Real-time reagent tracking with auto-consumption.
- **Mobile Phlebotomy View**: `/mobile/collections` - Touch-optimized collection workflow.
- **Batch Entry Worksheet**: `/worksheets/batch` - Spreadsheet-style result entry.
- **Workflow Queues**: `/queues` - Departmental worklist management.

### Fixed
- Hardened JSON parsing in database adapter to prevent crashes on malformed data.
- Added array validation for all API consumers to gracefully handle errors.
- Fixed template literal syntax errors in batch entry page.

---

## [v1.9.4] - 2025-12-19
### Added
- **Automatic Locking System**: Invisible, automatic record locking with 2-minute expiry.
- **Admin Lock Monitor**: `/admin/locks` for viewing and releasing locks.
- **Notification Timeouts**: Auto-dismiss alerts with configurable timeout.

### Changed
- Results Page: Dynamic lock status indication (removed manual check-in/out).

### Removed
- My Checkouts page (replaced by automatic locking).

---

## [v1.9.3] - 2025-12-19
### Added
- Department enforcement for test definitions.
- Read-only mode for cross-department result viewing.

## [v1.9.2] - 2025-12-19
### Changed
- UX: Grouped accessioning workflow.
- Admin: Enhanced department visibility.

## [v1.9.1] - 2025-12-19
### Added
- Mandatory MRN and Test Codes enforcement.
- Improved patient modification workflows.

## [v1.9.0] - 2025-12-19
### Added
- Full Admin UI for Test Definitions management.
