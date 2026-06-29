# Changelog

All notable changes to the Dx Clinical LIS project will be documented in this file.

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
