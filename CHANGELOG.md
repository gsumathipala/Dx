# Changelog

All notable changes to the Dx Clinical LIS project will be documented in this file.

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
