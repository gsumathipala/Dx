# Dx Clinical LIS - Complete System Architecture

> **Purpose**: This document provides a comprehensive blueprint for rebuilding the Dx Clinical Laboratory Information System from scratch.

---

## Table of Contents
1. [Technology Stack](#technology-stack)
2. [Project Structure](#project-structure)
3. [Database Schema](#database-schema)
4. [API Endpoints](#api-endpoints)
5. [Frontend Pages](#frontend-pages)
6. [Authentication & RBAC](#authentication--rbac)
7. [Theming System](#theming-system)
8. [Key Features](#key-features)
9. [Build & Run](#build--run)

---

## Technology Stack

| Category | Technology | Version |
|----------|-----------|---------|
| Framework | Next.js (App Router) | 16.0.10 |
| Language | TypeScript | 5.x |
| UI Library | React | 19.2.1 |
| Styling | Tailwind CSS | 3.4.1 |
| Charts | Recharts | 3.6.0 |
| Icons | Lucide React | 0.562.0 |
| Email | Nodemailer | 7.0.11 |
| Database | SQLite (via Drizzle ORM) | 3.x |
| ORM | Drizzle ORM | 0.30.x |

### Install Dependencies
```bash
npm install next@16.0.10 react@19.2.1 react-dom@19.2.1
npm install tailwindcss@3.4.1 autoprefixer postcss
npm install lucide-react recharts clsx tailwind-merge uuid
npm install nodemailer drizzle-orm better-sqlite3 dotenv
npm install -D typescript @types/react @types/node drizzle-kit
```

---

## Project Structure

```
clinical-lis/
├── drizzle/                    # Drizzle migrations
├── public/                     # Static assets
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── api/                # API routes (38 endpoints)
│   │   │   ├── admin/          # Admin APIs (14 endpoints)
│   │   │   ├── auth/           # Authentication
│   │   │   ├── orders/         # Order management
│   │   │   ├── patients/       # Patient CRUD
│   │   │   ├── results/        # Result entry
│   │   │   └── ...
│   │   ├── admin/              # Admin pages
│   │   ├── dashboard/          # Main dashboard
│   │   ├── accessioning/       # Sample registration
│   │   ├── results/            # Result entry
│   │   ├── tracking/           # Chain of custody
│   │   └── ...                 # 29 total page directories
│   ├── components/
│   │   ├── ui/                 # Reusable UI components
│   │   ├── reports/            # Report templates
│   │   ├── Sidebar.tsx         # Main navigation
│   │   └── AlertBanner.tsx     # System alerts
│   ├── context/
│   │   └── AuthContext.tsx     # Authentication provider
│   ├── db/
│   │   ├── index.ts            # Database connection
│   │   └── schema.ts           # Drizzle schema definitions
│   └── lib/
│       ├── db.ts               # Database utilities / adapter
│       └── utils.ts            # Helper functions
├── drizzle.config.ts           # Drizzle configuration
├── tailwind.config.js          # Tailwind + theming config
└── package.json
```

---

## Database Schema

The system uses a purely relational database schema managed by Drizzle ORM (`src/db/schema.ts`) on top of SQLite (`sqlite.db`).
Relationships are enforced via foreign keys where possible, but some complex nested structures (like test ingredients or result flags) are currently stored as JSON strings for flexibility.

### Core Tables

```typescript
// Defined in src/db/schema.ts

export const patients = sqliteTable('patients', {
  id: text('id').primaryKey(),
  firstName: text('first_name').notNull(),
  lastName: text('last_name').notNull(),
  dob: text('dob').notNull(),
  gender: text('gender').notNull(),
  mrn: text('mrn').notNull().unique(),
  // ... contact info
});

export const orders = sqliteTable('orders', {
  id: text('id').primaryKey(),
  patientId: text('patient_id').references(() => patients.id),
  accessionNumber: text('accession_number').unique(),
  status: text('status'),
  testIds: text('test_ids'), // stored as JSON array string
  // ... timestamps, priority
});

export const results = sqliteTable('results', {
  id: text('id').primaryKey(),
  orderId: text('order_id').references(() => orders.id),
  testId: text('test_id'),
  values: text('values'), // JSON encoded result values
  resultFlags: text('result_flags'), // JSON encoded flags
  status: text('status'), // Draft, Validated, etc
  // ... validators
});

export const users = sqliteTable('users', {
  id: text('id').primaryKey(),
  username: text('username').unique(),
  password: text('password'), // hashed (or plain for dev)
  role: text('role'),
  department: text('department'),
});
```

### Configuration Tables
- `testDefinitions`: detailed test config including ref ranges (JSON)
- `departments`: department metadata
- `authorizationQueues`: role-based access queues

### Inventory & QC
- `inventoryItems`, `inventoryTransactions`
- `qcMaterials`, `qcDefinitions`, `qcRuns`

### Equipment & Maintenance
- `equipment`, `equipmentLogs`

### Specialty Tables
- `histoBlocks`, `histoSlides`
- `microCultures`, `antibiotics`
- `recipes`, `productionRuns` (Manufacturing)

### System
- `auditLogs`, `systemAlerts`, `recordLocks`
- `messages`, `feedback`, `documents`


---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | User login |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/logout` | Logout |
| `/alerts` | System alerts |

### Core APIs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/orders` | Order management |
| GET/PUT | `/api/results` | Result entry |
| GET/POST | `/api/patients` | Patient CRUD |
| GET | `/api/dashboard/stats` | Dashboard aggregations (w/ optional `?department=`) |
| GET | `/api/dashboard/details` | Detailed lists (Pending, Completed, Critical, TAT) (w/ optional `?department=`) |
| GET | `/api/departments` | Returns list of active departments from test definitions |
| POST | `/api/messages` | Internal messaging |
| GET | `/api/tracking` | Chain of custody |

### Specialty APIs
| Endpoint | Description |
|----------|-------------|
| `/api/histology` | Histopathology module |
| `/api/microbiology` | Microbiology cultures |
| `/api/qc` | Quality control |
| `/api/equipment` | Equipment CRUD & Logs |
| `/api/middleware/ingest` | Instrument middleware |
| `/api/fhir` | FHIR interoperability |
| `/api/manufacturing` | Manufacturing/Production |

---

## Frontend Pages

### Main Workflow
| Route | Purpose |
|-------|---------|
| `/dashboard` | Main KPI dashboard |
| `/accessioning` | Sample registration |
| `/results` | Result entry & validation |
| `/tracking` | Chain of custody lookup |
| `/reports` | Report generation |

### Administration
| Route | Purpose |
|-------|---------|
| `/admin/users` | User management |
| `/admin/tests` | Test definitions |
| `/admin/settings` | System configuration |
| `/admin/departments` | Department management |
| `/admin/inventory` | Inventory control |
| `/admin/audit` | Audit log viewer |
| `/admin/locks` | Active lock monitor & release |
| `/admin/developer-docs` | Internal documentation |

### Specialty Modules
| Route | Purpose |
|-------|---------|
| `/histology` | Histopathology workflow |
| `/microbiology` | Microbiology cultures |
| `/qc` | QC dashboards |
| `/equipment` | Equipment Maintenance |
| `/worksheets` | Batch worksheets |
| `/manufacturing` | Reagent Production |

---

## Authentication & RBAC

### Cookie-Based Sessions
Authentication uses HTTP-only cookies with JSON session data:

```typescript
// Login sets cookie: auth_session
const session = {
  id: user.id,
  username: user.username,
  role: user.role,
  name: user.name,
  department: user.department
};
```

### Role Permissions
| Role | Dashboard | Accession | Results | Admin |
|------|-----------|-----------|---------|-------|
| admin | ✓ | ✓ | ✓ | ✓ |
| manager | ✓ | ✓ | ✓ | Partial |
| scientist | ✓ | ✓ | ✓ | ✗ |
| medic | ✓ | ✗ | View | ✗ |
| clerk | ✓ | ✓ | ✗ | ✗ |

### RBAC Implementation
```typescript
// In API routes:
const session = cookies().get('auth_session');
const user = JSON.parse(session.value);

if (!['admin', 'manager'].includes(user.role)) {
  return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
}
```

---

## Theming System

### CSS Variables (globals.css)
```css
:root {
  --primary-50: #eff6ff;
  --primary-500: #3b82f6;
  --primary-600: #2563eb;
  --primary-700: #1d4ed8;
  --slate-50: #f8fafc;
  --slate-900: #0f172a;
}

.theme-emerald {
  --primary-500: #10b981;
  --primary-600: #059669;
}

.theme-rose {
  --primary-500: #f43f5e;
  --primary-600: #e11d48;
}

.mode-dark {
  --slate-50: #0f172a;
  --slate-900: #f8fafc;
}
```

### Tailwind Config
```javascript
// tailwind.config.js
module.exports = {
  safelist: ['theme-blue', 'theme-emerald', 'theme-rose', 'mode-dark'],
  theme: {
    extend: {
      colors: {
        primary: {
          500: 'var(--primary-500)',
          600: 'var(--primary-600)',
        }
      }
    }
  }
}
```

### Client-Side Application
```typescript
// Settings page useEffect
useEffect(() => {
  const classesToRemove = Array.from(document.body.classList)
    .filter(cls => cls.startsWith('theme-') || cls.startsWith('mode-'));
  classesToRemove.forEach(cls => document.body.classList.remove(cls));
  
  document.body.classList.add(`theme-${settings.themeColor}`);
  if (settings.themeMode === 'dark') {
    document.body.classList.add('mode-dark');
  }
}, [settings.themeColor, settings.themeMode]);
```

---

## Key Features

### 1. Accessioning
- Patient lookup/creation
- Test selection with department routing
- Specimen type assignment
- Barcode/accession number generation

### 2. Result Entry
- Grid-based data entry
- Reference range flagging (H/L/HH/LL)
- Two-tier validation (Technical → Clinical)
- Auto-validation for normal results

### 3. Chain of Custody
- Full specimen tracking
- Location history
- Transfer logging
- Aliquot support

### 4. Reporting
- PDF generation
- Email delivery via SMTP
- Historical result trends
- Cumulative reports

### 5. Quality Control
- Westgard rules
- Levey-Jennings charts
- QC lot tracking

---

## Build & Run

### Development
```bash
npm run dev
# Opens on http://localhost:3000
```

### Production Build
```bash
npm run build
npm run start
```

### Default Users
| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | admin |
| manager | manager | manager |
| mlt | mlt | scientist |
| medic | medic | medic |

---

## Version History

| Version | Date | Features |
|---------|------|----------|
| v2.0.1 | 2025-12-27 | Critical Fixes (Persistence, Caching, Forms), Stability Improvement |
| v2.0.0 | 2025-12-19 | Major Release: SQLite, Billing, Inventory, Middleware |
| v1.9.5 | 2025-12-19 | Notification Timeouts (Elective Auto-Dismissal) |
| v1.9.4 | 2025-12-19 | Auto-Locking (Heartbeats, Admin Monitor), Removed My Checkouts |
| v1.9.3 | 2025-12-19 | Access Control (Dept Enforcement, Cross-Dept Read-Only) |
| v1.9.2 | 2025-12-19 | UX Enhancements (Grouped Accessioning, Admin/Dept Visibility) |
| v1.9.1 | 2025-12-19 | Data Integrity (Mandatory MRN, Test Codes, Patient Updates) |
| v1.9.0 | 2025-12-19 | Test Definition Management (Admin Edit/Delete UI) |
| v1.8.0 | 2025-12-18 | Microbiology AST Management (Admin Abx Config) |
| v1.7.0 | 2025-12-18 | Equipment Maintenance Module |
| v1.6.0 | 2025-12-18 | QC Modernization (Hierarchy, Custom Controls) |
| v1.5.1 | 2025-12-18 | Queue integration, Audit archiving UI fix |
| v1.5.0 | 2025-12-18 | Department governance, system-wide enforcement |
| v1.4.0 | 2025-12-18 | System-wide theming, dark mode |
| v1.3.0 | 2025-12-18 | Departments, SMTP, broadcasting |
| v1.9.6 | 2025-12-19 | Departmental Dashboards (Added Department Filtering, Dynamic Active Depts, Admin View Selector) |
| v1.9.5 | 2025-12-18 | Storage Management (Added Assign/Unassign samples, Location Contents) |
| v1.2.0 | 2025-12-18 | Messaging, email reports |
| v1.1.0 | 2025-12-18 | Trends, middleware API |
| v1.0.0 | 2025-12-18 | Core LIS functionality |
