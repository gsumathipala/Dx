# Dx Clinical LIS - Features

## Core Workflows

### Patient Management
- Register new patients with MRN, demographics, and contact info
- Search and update existing patient records
- Full audit trail of patient data changes

### Accessioning
- Create test orders with barcode generation
- Link specimens to orders
- Support for STAT and Routine priorities

### Result Entry & Verification
- Manual result entry with reference range validation
- Auto-flagging for critical/abnormal results
- 2-stage verification: Technical Validation → Clinical Verification

### Reporting
- Generate printable PDF reports
- View historical results by patient

---

## Advanced Modules

### Billing (v2.0)
- Automated invoice generation based on ordered tests
- CPT code mapping via `billing_items` table
- Invoice status tracking (Pending, Paid, Canceled)

### Inventory (v2.0)
- Real-time reagent and consumable tracking
- Automatic stock deduction on result entry
- Low-stock alerts based on configurable thresholds

### Instrument Integration (v2.0)
- TCP/IP middleware for HL7 ORU^R01 messages
- Automatic result ingestion from connected analyzers
- Configurable port (default: 6000)

---

## Specialized Views

### Mobile Phlebotomy (`/mobile/collections`)
- Touch-optimized interface for specimen collectors
- One-tap collection confirmation
- Pending order worklist

### Batch Entry (`/worksheets/batch`)
- Spreadsheet-style interface for high-volume entry
- Department-filtered worklists (Hematology, Chemistry, Urinalysis)
- Rapid save per test

### Workflow Queues (`/queues`)
- Role-based queue assignment
- Priority-sorted order lists
- Direct navigation to result entry

---

## Administration

### User Management (`/admin/users`)
- Create, edit, delete users
- Role assignment (Admin, Manager, Scientist, Medic, User)
- Department assignment

### Test Definitions (`/admin/tests`)
- Define test codes, names, units, reference ranges
- Assign to departments
- Set TAT targets

### Department Management (`/admin/departments`)
- Create and manage lab departments
- Enable/disable departments

### Lock Monitor (`/admin/locks`)
- View all active record locks
- Force-release locked records

---

## Security

- Bcrypt password hashing
- HTTPOnly session cookies
- Role-based access control (RBAC)
- Full audit logging for compliance
