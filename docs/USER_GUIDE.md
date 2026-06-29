# Dx LIS - User Guide

## Table of Contents
1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [User Roles](#user-roles)
4. [Workflow Guide](#workflow-guide)
5. [Results Module](#results-module)
6. [Verification Process](#verification-process)
7. [Reference Ranges & Flags](#reference-ranges--flags)
8. [Reports](#reports)
9. [Test Definitions](#test-definitions)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Dx LIS is an APHL 2019 compliant Laboratory Information System designed for clinical laboratories. It supports the complete testing lifecycle:

- **Pre-Analytical**: Patient registration, specimen accessioning, barcode labels
- **Analytical**: Result entry, reference range flagging, panic value alerts
- **Post-Analytical**: Two-tier verification, report generation

---

## Getting Started

### Accessing the System
Navigate to: `http://localhost:3000`

### Default Login Credentials

| Username | Password | Role | Description |
|----------|----------|------|-------------|
| `admin` | `admin123` | Admin | Full system access |
| `manager` | `manager` | Manager | Lab supervision, verification |
| `pathologist` | `path123` | Medic/Pathologist | Clinical verification (L2) |
| `mlt` | `mlt` | Scientist | Result entry, technical validation |
| `clerk` | `clerk123` | Clerk | Accessioning only |

---

## User Roles

### Administrator (`admin`)
- Full system access
- User management
- Test definition management
- System configuration

### Manager (`manager`)
- All scientist capabilities
- Clinical verification (Level 2)
- Queue management
- Force check-in records

### Medic/Pathologist (`medic`)
- Clinical verification (Level 2)
- View all results
- Approve and release reports
- Result entry (optional)

### Scientist/Lab Tech (`scientist`)
- Result entry
- Technical validation (Level 1)
- Submit for review
- Inventory management

### Clerk (`clerk`)
- Patient registration
- Specimen accessioning
- Generate barcode labels
- Cannot enter results

---

## Workflow Guide

### Pre-Analytical Phase

1. **Register Patient**
   - Navigate to: `Accessioning`
   - Search for existing patient or click "New Patient"
   - System performs fuzzy matching to detect duplicates
   - If duplicate detected, confirm or select existing patient

2. **Create Order**
   - Select patient
   - Choose tests to order
   - System generates unique accession number: `ACC-YYYYMMDD-XXXX`

3. **Print Labels**
   - Click "Print Label" on order
   - Supports ZPL (thermal printers) and HTML format
   - Label includes: Patient name, Accession #, Collection date

### Analytical Phase

4. **Enter Results**
   - Navigate to: `Results`
   - Select order from list
   - Click "Check Out to Edit" to lock record
   - Enter result values for each test
   - Select reagent lot numbers (traceability)
   - Add notes as needed

5. **Reference Range Flagging**
   - Results are automatically compared to reference ranges
   - Visual flags appear:
     - ✓ Normal (green)
     - ↓ Low (blue)
     - ↑ High (orange)
     - ⚠️ PANIC LOW/HIGH (red)

### Post-Analytical Phase

6. **Technical Validation (Level 1)**
   - Scientist clicks "Submit for Tech Validation"
   - Status changes to "Pending Validation"
   - Order moved to verification queue

7. **Clinical Verification (Level 2)**
   - Pathologist/Manager logs in
   - Reviews results in verification queue
   - Clicks "Clinical Verify & Release"
   - **IMPORTANT**: Must be different user than L1 validator
   - Status changes to "Completed"

8. **Print Report**
   - Print button enabled only after L2 verification
   - Reports show "FINAL" banner
   - Preliminary reports show warning banner

---

## Results Module

### Result Entry Screen

```
┌────────────────────────────────────────────────────┐
│  Hemoglobin                    LOINC: 718-7        │
│  ┌────────────────┐                                │
│  │ 14.5           │ g/dL   ✓ Normal               │
│  └────────────────┘                                │
│  Reference Range: 12.0-16.0 g/dL                   │
└────────────────────────────────────────────────────┘
```

### Check-In/Check-Out System

- **Check Out**: Lock record for editing (prevents concurrent edits)
- **Check In**: Release lock when done
- **Force Check-In**: Manager can override (requires reason)

### Queue Management

Orders can be assigned to queues:
- Pending Technical Validation
- Pending Clinical Verification
- Completed/Released

---

## Verification Process

### Two-Tier Verification (APHL 2019)

```
                    ┌─────────────────┐
                    │  Result Entry   │
                    │  (Scientist)    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Level 1: Tech   │
                    │ Validation      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Level 2: Clinical│
                    │ Verification    │
                    │ (DIFFERENT USER)│
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Report Released │
                    │ ✓ FINAL         │
                    └─────────────────┘
```

### Key Rules

1. **Same user cannot perform both L1 and L2**
   - System enforces this with error message
   - Ensures independent review

2. **Reports blocked until L2 complete**
   - Print button disabled
   - Shows "🔒 Print (Pending Verification)"

3. **Amendments require re-verification**
   - If result is changed after verification, status resets
   - Full L1→L2 cycle required again

---

## Reference Ranges & Flags

### Configured Test Definitions

| Test | LOINC | Range | Panic Low | Panic High |
|------|-------|-------|-----------|------------|
| Hemoglobin | 718-7 | 12-16 g/dL | 7.0 | 20.0 |
| Glucose Fasting | 1558-6 | 70-100 mg/dL | 40 | 500 |
| Creatinine | 2160-0 | 0.7-1.3 mg/dL | 0.3 | 10.0 |
| WBC | 6690-2 | 4.5-11.0 x10³/μL | 2.0 | 30.0 |
| Platelets | 777-3 | 150-400 x10³/μL | 50 | 1000 |
| Sodium | 2951-2 | 136-145 mmol/L | 120 | 160 |
| Potassium | 2823-3 | 3.5-5.0 mmol/L | 2.5 | 6.5 |
| TSH | 3016-3 | 0.4-4.0 mIU/L | 0.01 | 100 |
| HbA1c | 4548-4 | 4.0-5.6% | - | 15.0 |
| ALT | 1742-6 | 7-56 U/L | - | 1000 |

### Flag Colors

| Flag | Meaning | Action |
|------|---------|--------|
| ✓ Normal | Within reference range | No action needed |
| ↓ Low | Below minimum | Review clinically |
| ↑ High | Above maximum | Review clinically |
| ⚠️ PANIC | Critical value | **IMMEDIATE notification** |

---

## Reports

### Report Types

1. **Patient Report**
   - Individual patient results
   - Shows PRELIMINARY or FINAL status
   - Includes reference ranges and flags
   - QR code for verification

2. **Certificate of Analysis (COA)**
   - Formal certificate format
   - Includes lot numbers for traceability
   - ISO 15189 compliance footer

### Status Banners

- **PRELIMINARY** (Red): Not verified - NOT FOR CLINICAL USE
- **FINAL** (Green): Clinically verified - Safe for use

---

## Test Definitions

### Adding New Tests

Admin → Test Definitions → Add New

Required fields:
- **Name**: Display name (e.g., "Hemoglobin")
- **Code**: Short code (e.g., "HGB")
- **Units**: Measurement units (e.g., "g/dL")
- **Reference Range**: Normal range
- **TAT Hours**: Target turnaround time

Optional fields:
- **LOINC Code**: For interoperability
- **Department**: Chemistry, Hematology, etc.
- **Methodology**: Testing method
- **Panic Values**: Critical high/low thresholds

---

## Troubleshooting

### Common Issues

**Q: "Record is locked by another user"**
- Another user has checked out the record
- Wait for them to check in, or ask Manager to force check-in

**Q: "Two-Tier Violation" error**
- You cannot verify results you entered
- A different user must perform L2 verification

**Q: Print button is disabled**
- Results not yet clinically verified
- Complete L2 verification first

**Q: Duplicate patient warning**
- System detected similar patient
- Review matches and select existing or create new

**Q: Result shows PANIC flag**
- Critical value detected
- Notify clinician immediately per protocol

---

## API Endpoints

For system integrations:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/patients` | GET, POST, PUT | Patient management |
| `/api/orders` | GET, POST | Order management |
| `/api/specimens` | GET, POST, PUT | Specimen tracking |
| `/api/results` | GET, POST | Result entry & verification |
| `/api/labels` | GET, POST | Barcode label generation |
| `/api/admin/tests` | GET, POST, PUT, DELETE | Test definitions |

---

## Support

For technical support, contact your system administrator.

**Dx LIS v2.0.1**  
APHL 2019 Compliant | ISO 15189:2012 Ready
