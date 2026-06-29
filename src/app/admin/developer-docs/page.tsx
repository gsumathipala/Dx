"use client";

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import {
    Book, Database, Server, Code, Layout, Shield,
    Globe, Cpu, AlertTriangle, Workflow, Palette,
    LifeBuoy, GitBranch, Box, Activity, Zap
} from 'lucide-react';

export default function DeveloperDocsPage() {
    const [activeTab, setActiveTab] = useState('architecture');

    const tabs = [
        {
            group: 'Core', items: [
                { id: 'architecture', label: 'System Architecture', icon: Layout },
                { id: 'database', label: 'Database Schema', icon: Database },
                { id: 'api', label: 'API Reference', icon: Globe },
            ]
        },
        {
            group: 'Logic', items: [
                { id: 'backend', label: 'Backend Logic', icon: Cpu },
                { id: 'clinical', label: 'Clinical Engine', icon: Zap },
                { id: 'workflows', label: 'Workflows', icon: Workflow },
                { id: 'security', label: 'Security & Auth', icon: Shield },
            ]
        },
        {
            group: 'Frontend', items: [
                { id: 'design', label: 'Design System', icon: Palette },
                { id: 'components', label: 'Component Library', icon: Box },
            ]
        },
        {
            group: 'Ops', items: [
                { id: 'deployment', label: 'Deployment & DevOps', icon: Server },
                { id: 'troubleshooting', label: 'Troubleshooting', icon: LifeBuoy },
            ]
        },
        {
            group: 'Project', items: [
                { id: 'blueprint', label: 'System Blueprint', icon: Book },
                { id: 'history', label: 'Changelog & Features', icon: GitBranch },
            ]
        }
    ];

    return (
        <div className="flex gap-6 h-[calc(100vh-100px)]">
            {/* Sidebar Navigation */}
            <div className="w-80 flex-shrink-0 border-r pr-6 flex flex-col h-full bg-slate-50/50 p-4 rounded-lg">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold flex items-center gap-2 text-slate-900">
                        <Code className="w-7 h-7 text-primary-600" />
                        Dev Bible
                    </h1>
                    <p className="text-xs text-slate-500 mt-1">Dx LIS Technical Reference</p>
                </div>

                <div className="flex-1 overflow-y-auto space-y-6">
                    {tabs.map((group, idx) => (
                        <div key={idx}>
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 px-2">{group.group}</h3>
                            <div className="space-y-1">
                                {group.items.map(tab => (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`w-full flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md transition-all ${activeTab === tab.id
                                            ? 'bg-white text-primary-700 shadow border border-primary-100'
                                            : 'text-slate-600 hover:bg-slate-200'
                                            }`}
                                    >
                                        <tab.icon className={`w-4 h-4 ${activeTab === tab.id ? 'text-primary-600' : 'text-slate-400'}`} />
                                        {tab.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto pr-4 custom-scrollbar">
                <div className="max-w-5xl space-y-12 pb-20">
                    {activeTab === 'architecture' && <ArchitectureSection />}
                    {activeTab === 'database' && <DatabaseSection />}
                    {activeTab === 'api' && <ApiSection />}
                    {activeTab === 'backend' && <BackendLogicSection />}
                    {activeTab === 'clinical' && <ClinicalEngineSection />}
                    {activeTab === 'workflows' && <WorkflowsSection />}
                    {activeTab === 'security' && <SecuritySection />}
                    {activeTab === 'design' && <DesignSystemSection />}
                    {activeTab === 'components' && <ComponentsSection />}
                    {activeTab === 'deployment' && <DeploymentSection />}
                    {activeTab === 'troubleshooting' && <TroubleshootingSection />}
                    {activeTab === 'blueprint' && <BlueprintSection />}
                    {activeTab === 'history' && <ChangelogSection />}
                </div>
            </div>
        </div>
    );
}

// ==========================================
// 1. ARCHITECTURE
// ==========================================
function ArchitectureSection() {
    return (
        <section className="space-y-8">
            <Header title="System Architecture" subtitle="High-level overview of the application stack, data flow, and design patterns." />

            <Card title="The Modular Monolith">
                <div className="prose prose-sm max-w-none text-slate-700">
                    <p>
                        Dx LIS is a <strong>Modular Monolith</strong> built on Next.js App Router. A clinical LIS
                        often operates in air-gapped or resource-constrained environments where orchestration overhead is a
                        liability, so the entire system — UI, API, clinical decision engine, and storage — ships as one
                        deployable Node.js process backed by a single SQLite file.
                    </p>
                    <p className="mt-2"><strong>Key design principles:</strong></p>
                    <ul className="list-disc pl-5">
                        <li><strong>Zero external dependencies:</strong> No Redis, no Postgres, no external auth provider. SQLite (better-sqlite3) is the single source of truth, accessed through Drizzle ORM.</li>
                        <li><strong>Server-authoritative writes:</strong> Accession numbers, signatures, audit entries, and clinical-engine evaluations are all generated server-side. The client never computes anything compliance-relevant.</li>
                        <li><strong>Clinical engine as a library:</strong> Delta checks, critical values, reflex rules, and notifiable-condition surveillance live in <code>src/lib/clinical-engine.ts</code> and are invoked from the results API — not duplicated per route.</li>
                        <li><strong>Progressive migration:</strong> Older routes use the legacy <code>readDb()/writeDb()</code> whole-DB snapshot helpers; newer routes query Drizzle directly. Both read the same SQLite file (see Backend Logic).</li>
                    </ul>
                </div>
            </Card>

            <div className="grid md:grid-cols-2 gap-6">
                <Card title="Request Lifecycle (Result Entry)">
                    <div className="text-xs font-mono space-y-2">
                        <div className="bg-slate-100 p-2 rounded border border-slate-200">
                            1. CLIENT: Result grid submit (POST /api/results)
                        </div>
                        <div className="flex justify-center"><ArrowDown /></div>
                        <div className="bg-amber-50 p-2 rounded border border-amber-200">
                            2. AUTH: auth_session / auth_token cookie resolved to user
                        </div>
                        <div className="flex justify-center"><ArrowDown /></div>
                        <div className="bg-blue-50 p-2 rounded border border-blue-200">
                            3. UPSERT: per-test result rows written via Drizzle
                        </div>
                        <div className="flex justify-center"><ArrowDown /></div>
                        <div className="bg-purple-50 p-2 rounded border border-purple-200">
                            4. CLINICAL ENGINE: delta / critical / reflex / notifiable (async)
                        </div>
                        <div className="flex justify-center"><ArrowDown /></div>
                        <div className="bg-green-50 p-2 rounded border border-green-200">
                            5. ORDER: status transition + completedAt + e-signature
                        </div>
                        <div className="flex justify-center"><ArrowDown /></div>
                        <div className="bg-slate-800 text-white p-2 rounded border border-slate-900">
                            6. AUDIT: immutable audit_logs row
                        </div>
                    </div>
                </Card>
                <Card title="Technology Choice Rationale">
                    <table className="w-full text-xs text-left">
                        <thead><tr className="border-b"><th className="pb-2">Tech</th><th className="pb-2">Rationale</th></tr></thead>
                        <tbody className="divide-y">
                            <tr><td className="py-2 font-bold">Next.js 16</td><td>Unified frontend/backend, file-based API routes, single deploy artifact.</td></tr>
                            <tr><td className="py-2 font-bold">SQLite + Drizzle</td><td>Zero-setup relational store with typed queries; one file to back up; survives power loss better than flat JSON.</td></tr>
                            <tr><td className="py-2 font-bold">Tailwind CSS</td><td>Utility classes + CSS-variable theming for the 5 colour schemes and dark mode.</td></tr>
                            <tr><td className="py-2 font-bold">Recharts</td><td>KPI dashboard and patient trend charts.</td></tr>
                            <tr><td className="py-2 font-bold">bcryptjs</td><td>Password hashing with transparent legacy-password upgrade on login.</td></tr>
                            <tr><td className="py-2 font-bold">Lucide</td><td>Consistent SVG icon set with tree-shaking.</td></tr>
                        </tbody>
                    </table>
                </Card>
            </div>

            <Card title="Source Layout">
                <pre className="bg-slate-900 text-slate-200 p-4 rounded text-xs overflow-x-auto">{`src/
├── app/                    # Pages — 60+ routes (App Router)
│   ├── api/                # ~100 API endpoints (route.ts files)
│   ├── accessioning/       # Order entry
│   ├── receiving/          # Specimen receiving workflow
│   ├── results/            # Result entry + validation grid
│   ├── critical-values/    # Critical value notification inbox
│   ├── reports/            # Branded report viewer (+ /cumulative)
│   ├── phlebotomy/         # Collection scheduling
│   ├── epidemiology/       # Notifiable disease workflow
│   └── admin/              # 20+ admin configuration pages
├── components/
│   ├── ui/                 # Card, Badge, Table, Button, Input...
│   ├── reports/            # PatientReport, CoaReport print layouts
│   └── Sidebar.tsx         # Role-aware navigation
├── db/
│   ├── index.ts            # Drizzle + better-sqlite3 init (sqlite_v2.db)
│   └── schema.ts           # 59 table definitions
├── lib/
│   ├── db.ts               # Legacy readDb()/writeDb() snapshot + logAudit
│   ├── auth.ts             # getAuthUser() unified cookie resolution
│   ├── clinical-engine.ts  # Delta / critical / reflex / epi / demographics
│   ├── accession.ts        # Sequential accession number generation
│   └── inventory.ts        # Reagent consumption on result entry
└── scripts/                # Migrations, seeding, password hashing`}</pre>
            </Card>
        </section>
    );
}

// ==========================================
// 2. DATABASE DEEP DIVE
// ==========================================
function DatabaseSection() {
    return (
        <section className="space-y-8">
            <Header title="Database Schema Dictionary" subtitle="59 tables in sqlite_v2.db, defined in src/db/schema.ts via Drizzle ORM. Grouped by domain below; key tables documented in full." />

            <Card title="Table Inventory by Domain">
                <div className="grid md:grid-cols-2 gap-4 text-xs">
                    <div className="bg-blue-50 p-3 rounded border border-blue-200">
                        <h4 className="font-bold text-blue-800 mb-2">Core Clinical</h4>
                        <p className="font-mono text-blue-700">users, sessions, departments, patients, orders, specimens, results, test_definitions, authorization_queues, audit_logs</p>
                    </div>
                    <div className="bg-red-50 p-3 rounded border border-red-200">
                        <h4 className="font-bold text-red-800 mb-2">Clinical Decision Engine</h4>
                        <p className="font-mono text-red-700">delta_check_rules, delta_check_flags, critical_value_notifications, critical_value_acknowledgments, reflex_rules, reflex_activations, demographic_reference_ranges, calculated_tests</p>
                    </div>
                    <div className="bg-green-50 p-3 rounded border border-green-200">
                        <h4 className="font-bold text-green-800 mb-2">Pre-analytical</h4>
                        <p className="font-mono text-green-700">specimen_receiving, phlebotomy_schedules, rejection_criteria, retention_policies, specimen_disposals</p>
                    </div>
                    <div className="bg-purple-50 p-3 rounded border border-purple-200">
                        <h4 className="font-bold text-purple-800 mb-2">Post-analytical & Compliance</h4>
                        <p className="font-mono text-purple-700">result_signatures, tat_thresholds, tat_breaches, user_competencies, distribution_rules, distribution_logs, requesters, notifiable_conditions, epidemiology_notifications, loinc_codes</p>
                    </div>
                    <div className="bg-amber-50 p-3 rounded border border-amber-200">
                        <h4 className="font-bold text-amber-800 mb-2">Quality & Equipment</h4>
                        <p className="font-mono text-amber-700">qc_materials, qc_definitions, qc_runs, equipment, equipment_logs, record_locks, worksheets, workstations, routing_rules, routing_assignments</p>
                    </div>
                    <div className="bg-slate-100 p-3 rounded border border-slate-300">
                        <h4 className="font-bold text-slate-800 mb-2">Operations & Modules</h4>
                        <p className="font-mono text-slate-700">billing_items, invoices, inventory_items, inventory_transactions, messages, feedback, documents, email_queue, system_alerts, settings, histo_blocks, histo_slides, micro_cultures, antibiotics, recipes, production_runs</p>
                    </div>
                </div>
            </Card>

            <SchemaItem
                name="patients"
                desc="Core entity representing the human subject of testing."
                fields={[
                    { name: 'id', type: 'TEXT PK', desc: 'UUID primary key' },
                    { name: 'mrn', type: 'TEXT UNIQUE', desc: 'Hospital Medical Record Number' },
                    { name: 'firstName / lastName', type: 'TEXT', desc: 'Name (stored as separate columns)' },
                    { name: 'dob', type: 'TEXT', desc: 'YYYY-MM-DD' },
                    { name: 'gender', type: 'TEXT', desc: "'Male' | 'Female' | 'Other'" },
                    { name: 'email / phone / address', type: 'TEXT?', desc: 'Optional contact details' }
                ]}
            />

            <SchemaItem
                name="orders"
                desc="A request for laboratory services. Links a patient to one or more tests. The accession number is generated server-side and is the human-facing identifier."
                fields={[
                    { name: 'id', type: 'TEXT PK', desc: 'UUID' },
                    { name: 'accessionNumber', type: 'TEXT UNIQUE', desc: 'Sequential, format YYYY-MM-DD-XXXX, generated in src/lib/accession.ts' },
                    { name: 'patientId', type: 'TEXT FK', desc: '→ patients.id' },
                    { name: 'testIds', type: 'TEXT (JSON)', desc: 'JSON array of test_definitions ids, e.g. ["test-hgb","test-glu"]. Reflex rules append to this.' },
                    { name: 'status', type: 'TEXT', desc: "'Preliminary' → 'Pending Validation' → 'Technically Validated' → 'Completed'. Status strings are case-sensitive — always capitalised." },
                    { name: 'priority', type: 'TEXT', desc: "'Routine' (default) | 'STAT'" },
                    { name: 'queueId', type: 'TEXT?', desc: '→ authorization_queues.id, set during validation routing' },
                    { name: 'timestamp', type: 'TEXT', desc: 'ISO 8601 order-creation time. NOTE: there is no createdAt column — always use timestamp.' },
                    { name: 'completedAt', type: 'TEXT?', desc: 'Set when clinical verification completes the order. Basis of TAT calculations.' },
                    { name: 'updatedAt', type: 'TEXT?', desc: 'Last mutation time' }
                ]}
            />

            <SchemaItem
                name="results"
                desc={'One row per (order, test). The values column is a JSON object {"value": "..."}. A pseudo-row with testId=REPORT carries report-level notes.'}
                fields={[
                    { name: 'id', type: 'TEXT PK', desc: 'UUID' },
                    { name: 'orderId', type: 'TEXT FK', desc: '→ orders.id' },
                    { name: 'testId', type: 'TEXT', desc: "test_definitions id, or the literal 'REPORT' for note rows" },
                    { name: 'values', type: 'TEXT (JSON)', desc: '{"value":"520"} — stringified on write, parsed on read' },
                    { name: 'status', type: 'TEXT', desc: "Mirrors the action: 'Resulted' | 'Pending Validation' | 'Technically Validated' | 'Clinically Verified'" },
                    { name: 'technicalValidatedBy', type: 'TEXT?', desc: 'Username, set by TECHNICAL_VALIDATE action' },
                    { name: 'clinicalVerifiedBy', type: 'TEXT?', desc: 'Username, set by CLINICAL_VERIFY action' },
                    { name: 'comments', type: 'TEXT?', desc: 'Report notes (REPORT row)' },
                    { name: 'timestamp', type: 'TEXT', desc: 'ISO 8601 entry time' }
                ]}
            />

            <SchemaItem
                name="test_definitions"
                desc="The test catalogue. The referenceRange JSON shape below is the canonical contract used by the clinical engine, report flagging, and the admin Tests page — do not invent alternative keys."
                fields={[
                    { name: 'id', type: 'TEXT PK', desc: "e.g. 'test-hgb'" },
                    { name: 'code', type: 'TEXT UNIQUE', desc: "Short code, e.g. 'HGB'" },
                    { name: 'name', type: 'TEXT', desc: "Display name, e.g. 'Hemoglobin'" },
                    { name: 'department', type: 'TEXT', desc: 'Owning department code' },
                    { name: 'units', type: 'TEXT?', desc: "e.g. 'g/dL'" },
                    { name: 'referenceRange', type: 'TEXT (JSON)', desc: 'CANONICAL SHAPE: { min, max, panicLow, panicHigh, unit, text }. panicLow/panicHigh drive critical value detection.' },
                    { name: 'loincCode', type: 'TEXT?', desc: 'Linked via the LOINC admin page' }
                ]}
            />

            <SchemaItem
                name="critical_value_notifications"
                desc="Auto-created by the clinical engine when a numeric result crosses panicLow/panicHigh. Drives the Critical Values inbox and the dashboard critical count (Pending only)."
                fields={[
                    { name: 'id', type: 'TEXT PK', desc: 'UUID' },
                    { name: 'orderId / patientId / testId', type: 'TEXT', desc: 'Context keys' },
                    { name: 'value', type: 'TEXT', desc: 'The offending value' },
                    { name: 'threshold', type: 'TEXT', desc: "Human-readable, e.g. '> 500 mg/dL'" },
                    { name: 'criticalType', type: 'TEXT', desc: "'HIGH' | 'LOW'" },
                    { name: 'status', type: 'TEXT', desc: "'Pending' → 'Acknowledged' (via /api/critical-values/[id]/ack)" },
                    { name: 'createdAt / createdBy', type: 'TEXT', desc: 'Detection time and the user who entered the result' }
                ]}
            />

            <SchemaItem
                name="delta_check_rules / delta_check_flags"
                desc="Rules define a permitted change between consecutive results for the same patient+test; flags record violations."
                fields={[
                    { name: 'rules.testId / testCode', type: 'TEXT', desc: 'Which analyte the rule watches (both required by the API)' },
                    { name: 'rules.deltaType', type: 'TEXT', desc: "'percent' | 'absolute'" },
                    { name: 'rules.threshold', type: 'REAL', desc: 'Change magnitude that triggers a flag' },
                    { name: 'rules.direction', type: 'TEXT', desc: "'any' | 'increase' | 'decrease'" },
                    { name: 'flags.previousValue / currentValue', type: 'REAL', desc: 'The compared pair' },
                    { name: 'flags.deltaPercent / deltaAbsolute', type: 'REAL', desc: 'Computed deltas at flag time' }
                ]}
            />

            <SchemaItem
                name="reflex_rules / reflex_activations"
                desc="Conditional add-on testing. When a trigger test's value satisfies the condition, the engine records an activation AND appends addTestId to the order's testIds."
                fields={[
                    { name: 'rules.triggerTestId', type: 'TEXT', desc: 'Watched analyte' },
                    { name: 'rules.triggerCondition', type: 'TEXT (JSON)', desc: '{ "operator": ">|<|>=|<=|==", "value": number } — sent as an OBJECT by the UI, stringified in storage' },
                    { name: 'rules.addTestId', type: 'TEXT', desc: 'Test automatically added to the order' },
                    { name: 'activations.status', type: 'TEXT', desc: "'Pending' once fired; deduplicated per (order, rule)" }
                ]}
            />

            <SchemaItem
                name="result_signatures"
                desc="Electronic signature trail. Inserted automatically by POST /api/results on TECHNICAL_VALIDATE and CLINICAL_VERIFY actions; rendered on printed reports."
                fields={[
                    { name: 'orderId', type: 'TEXT', desc: 'Signed order' },
                    { name: 'signedBy', type: 'TEXT', desc: 'Display name of validating user' },
                    { name: 'signatureType', type: 'TEXT', desc: "'technical' | 'clinical'" },
                    { name: 'signedAt', type: 'TEXT', desc: 'ISO 8601' },
                    { name: 'ipAddress / userAgent', type: 'TEXT?', desc: 'Captured from request headers for non-repudiation' }
                ]}
            />

            <SchemaItem
                name="notifiable_conditions / epidemiology_notifications"
                desc="Public-health surveillance. Conditions link diseases to test ids; the clinical engine auto-creates a Pending notification when any linked test is resulted."
                fields={[
                    { name: 'conditions.testIds', type: 'TEXT (JSON)', desc: 'Array of test_definitions ids that indicate the condition' },
                    { name: 'conditions.reportingBody', type: 'TEXT', desc: "e.g. 'Ministry of Health'" },
                    { name: 'notifications.status', type: 'TEXT', desc: "'Pending' → 'Reviewed' → 'Submitted' → 'Closed' (manager/admin workflow)" },
                    { name: 'notifications.detectedAt', type: 'TEXT', desc: 'Auto-detection timestamp' }
                ]}
            />

            <Card title="Conventions">
                <ul className="list-disc pl-5 text-sm text-slate-700 space-y-2">
                    <li><strong>IDs:</strong> UUID v4 strings everywhere except seeded config rows (<code>test-hgb</code>, <code>admin</code>).</li>
                    <li><strong>Timestamps:</strong> ISO 8601 strings in TEXT columns (SQLite has no native datetime). <code>sessions.expiresAt</code> is the one exception — epoch milliseconds INTEGER.</li>
                    <li><strong>JSON-in-TEXT:</strong> <code>orders.testIds</code>, <code>results.values</code>, <code>test_definitions.referenceRange</code>, <code>reflex_rules.triggerCondition</code>, <code>notifiable_conditions.testIds</code>. The legacy <code>readDb()</code> parses these on read; direct Drizzle queries must <code>JSON.parse</code> manually.</li>
                    <li><strong>Status casing:</strong> Order statuses are capitalised (<code>&apos;Completed&apos;</code>, not <code>&apos;completed&apos;</code>). Lowercase comparisons silently match nothing — this has caused real bugs.</li>
                    <li><strong>Booleans:</strong> Drizzle <code>integer(..., {'{'} mode: &apos;boolean&apos; {'}'})</code> columns (0/1 in SQLite).</li>
                </ul>
            </Card>
        </section>
    );
}

// ==========================================
// 3. API REFERENCE
// ==========================================
function ApiSection() {
    return (
        <section className="space-y-8">
            <Header title="REST API Reference" subtitle="~100 endpoints under /api. All bodies are JSON. All routes require an authenticated session cookie unless noted; mutations on config resources require admin or manager role." />

            <Card title="Endpoint Catalogue">
                <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 border-b"><tr><th className="p-2">Area</th><th className="p-2">Endpoints</th><th className="p-2">Notes</th></tr></thead>
                    <tbody className="divide-y">
                        <tr><td className="p-2 font-bold">Auth</td><td className="p-2 font-mono">/api/auth/login · logout · me</td><td className="p-2">Sets both auth cookies; me resolves session</td></tr>
                        <tr><td className="p-2 font-bold">Patients</td><td className="p-2 font-mono">/api/patients [?q=] · /api/patients/[id]/history · /api/patient-360</td><td className="p-2">GET/POST/PUT; fuzzy search via q</td></tr>
                        <tr><td className="p-2 font-bold">Orders</td><td className="p-2 font-mono">/api/orders [?patientId=]</td><td className="p-2">GET enriches patientName/Mrn/Dob/Gender; POST creates order + specimens + audit</td></tr>
                        <tr><td className="p-2 font-bold">Results</td><td className="p-2 font-mono">/api/results [?orderId=] · /api/results/ingest</td><td className="p-2">POST drives the whole validation workflow (see block below); ingest is the analyzer bridge</td></tr>
                        <tr><td className="p-2 font-bold">Receiving</td><td className="p-2 font-mono">/api/receiving [?status=]</td><td className="p-2">Specimen accept/reject with condition + temperature + volume</td></tr>
                        <tr><td className="p-2 font-bold">Critical values</td><td className="p-2 font-mono">/api/critical-values [?status=] · /[id]/ack</td><td className="p-2">Auto-created by engine; ack records clinician + method + read-back notes</td></tr>
                        <tr><td className="p-2 font-bold">Delta checks</td><td className="p-2 font-mono">/api/delta-checks/rules · /rules/[id] · /flags</td><td className="p-2">Rule CRUD + flag inbox</td></tr>
                        <tr><td className="p-2 font-bold">Reflex rules</td><td className="p-2 font-mono">/api/reflex-rules · /[id]</td><td className="p-2">triggerCondition is an object in request bodies</td></tr>
                        <tr><td className="p-2 font-bold">Reports</td><td className="p-2 font-mono">/api/reports/cumulative?patientId= · /api/signatures?orderId=</td><td className="p-2">Flowsheet grid; e-signature list for report footer</td></tr>
                        <tr><td className="p-2 font-bold">Dashboards</td><td className="p-2 font-mono">/api/dashboard/stats · /details?type= · /api/kpi · /api/tat-monitor</td><td className="p-2">type ∈ PENDING|COMPLETED|CRITICAL|TAT; optional ?department=</td></tr>
                        <tr><td className="p-2 font-bold">Scheduling</td><td className="p-2 font-mono">/api/phlebotomy · /[id]</td><td className="p-2">Requires patientId, wardLocation, scheduledAt, collectionType</td></tr>
                        <tr><td className="p-2 font-bold">Surveillance</td><td className="p-2 font-mono">/api/epidemiology · /[id] · /api/notifiable-conditions · /[id]</td><td className="p-2">Notification status transitions are manager/admin only</td></tr>
                        <tr><td className="p-2 font-bold">Compliance</td><td className="p-2 font-mono">/api/tat-thresholds · /api/competency · /api/retention (+ /dispose) · /api/loinc · /api/demographic-ranges · /api/requesters · /api/distribution-rules</td><td className="p-2">Config CRUD, each with a matching admin page</td></tr>
                        <tr><td className="p-2 font-bold">Lab ops</td><td className="p-2 font-mono">/api/queues · /api/specimens · /api/worksheets · /api/qc · /api/equipment · /api/inventory · /api/storage · /api/locks · /api/tracking · /api/coc</td><td className="p-2">Worklists, QC runs, checkout locking, chain of custody</td></tr>
                        <tr><td className="p-2 font-bold">Modules</td><td className="p-2 font-mono">/api/microbiology · /api/histology · /api/billing · /api/manufacturing · /api/messages · /api/documents · /api/feedback</td><td className="p-2">Departmental modules</td></tr>
                        <tr><td className="p-2 font-bold">Admin</td><td className="p-2 font-mono">/api/admin/tests · users · departments · settings · audit · backup · restore · criteria · comments · maintenance</td><td className="p-2">PUT /api/admin/tests takes id in the BODY (no /[id] route)</td></tr>
                        <tr><td className="p-2 font-bold">Integration</td><td className="p-2 font-mono">/api/middleware/ingest · /transmit · /api/fhir/diagnostic-report · /api/labels</td><td className="p-2">Analyzer bridge, FHIR export, ZPL label generation</td></tr>
                    </tbody>
                </table>
            </Card>

            <div className="space-y-4">
                <ApiBlock
                    method="POST"
                    route="/api/auth/login"
                    desc="Authenticate and establish session"
                    body={`{ "username": "admin", "password": "admin123" }`}
                    response={`// 200 — also sets TWO httpOnly cookies:
//   auth_token   = session UUID  (sessions table)
//   auth_session = JSON user object (legacy routes)
{
  "id": "admin",
  "username": "admin",
  "role": "admin",
  "name": "System Administrator",
  "department": null
}`}
                />

                <ApiBlock
                    method="POST"
                    route="/api/orders"
                    desc="Create order + specimens (accession number generated server-side)"
                    body={`{
  "patientId": "uuid",
  "testIds": ["test-hgb", "test-glu"],
  "priority": "STAT",          // or "Routine"
  "samples": [
    { "type": "Whole Blood", "condition": "Good", "location": "Reception" }
  ]
}`}
                    response={`// 201
{
  "id": "uuid",
  "accessionNumber": "2026-06-11-0001",
  "status": "Preliminary",
  "timestamp": "2026-06-11T11:26:48.041Z",
  ...
}`}
                />

                <ApiBlock
                    method="GET"
                    route="/api/orders"
                    desc="List orders, enriched with patient display fields"
                    queries={[
                        { param: 'patientId', desc: 'Filter to one patient' }
                    ]}
                    response={`[
  {
    "id": "...", "accessionNumber": "2026-06-11-0001",
    "status": "Completed", "priority": "STAT",
    "testIds": ["test-hgb","test-glu"],
    "timestamp": "...", "completedAt": "...",
    "patientName": "Tester, QA",   // ← enriched
    "patientMrn": "QA-001",
    "patientDob": "1985-03-15",
    "patientGender": "Female"
  }
]`}
                />

                <ApiBlock
                    method="POST"
                    route="/api/results"
                    desc="THE workflow endpoint — entry, validation, verification"
                    body={`{
  "orderId": "uuid",
  "values": {
    "results": { "test-glu": "520", "test-hgb": "13.5" },
    "notes": "optional report note"
  },
  // Pick ONE of these modes:
  "status": "Pending Validation",   // initial entry
  "action": "TECHNICAL_VALIDATE",   // tech sign-off
  "action": "CLINICAL_VERIFY",      // completes the order
  "queueId": "optional-queue-routing"
}`}
                    response={`// 200 — side effects depend on mode:
// initial entry  → clinical engine fires (delta/critical/
//                  reflex/notifiable) per numeric value
// TECHNICAL_VALIDATE → 'technical' e-signature recorded
// CLINICAL_VERIFY    → order status 'Completed',
//                      completedAt set, 'clinical' signature
{ "success": true }`}
                />

                <ApiBlock
                    method="POST"
                    route="/api/receiving"
                    desc="Receive (accept/reject) a specimen"
                    body={`{
  "specimenId": "uuid",
  "orderId": "uuid",
  "condition": "Acceptable",   // 'Marginal' → Recollection-Required
                               // 'Rejected' → Rejected
  "conditionNotes": "",
  "rejectionReason": "",       // required when Rejected
  "temperature": "4C",
  "volume": "5"
}`}
                    response={`// 201
{ "id": "uuid", "status": "Accepted" }`}
                />

                <ApiBlock
                    method="POST"
                    route="/api/critical-values/[id]/ack"
                    desc="Acknowledge a critical value (read-back documentation)"
                    body={`{
  "notifiedClinician": "Dr. House",
  "notificationMethod": "phone",   // phone | fax | in-person
  "notes": "Read-back confirmed"
}`}
                    response={`{
  "success": true,
  "acknowledgment": {
    "acknowledgedBy": "admin",
    "acknowledgedAt": "2026-06-11T11:33:01.245Z",
    ...
  }
}`}
                />

                <ApiBlock
                    method="POST"
                    route="/api/middleware/ingest"
                    desc="Analyzer interface (ASTM/HL7 → JSON bridge)"
                    body={`{
  "instrumentId": "BECKMAN-DXI",
  "apiKey": "sk_prod_...",
  "results": [
    { "sampleId": "2026-06-11-0001", "test": "TSH",
      "value": 4.5, "unit": "uIU/mL", "flag": "H" }
  ]
}`}
                    response={`{ "success": true, "processed": 1 }`}
                />
            </div>

            <AlertBox type="info" title="Validation contract gotchas (verified during QA)">
                <ul className="list-disc pl-4 space-y-1 text-sm">
                    <li><code>delta-checks/rules</code> POST requires <strong>both</strong> <code>testId</code> and <code>testCode</code>.</li>
                    <li><code>reflex-rules</code> POST takes <code>triggerCondition</code> as an <strong>object</strong>, not a JSON string.</li>
                    <li><code>phlebotomy</code> POST requires <code>patientId, wardLocation, scheduledAt, collectionType</code>.</li>
                    <li><code>tat-thresholds</code> POST requires <code>scope, targetHours, warningHours, breachHours</code>.</li>
                    <li><code>competency</code> POST requires <code>userId, competencyDate, expiryDate</code>.</li>
                    <li><code>PUT /api/admin/tests</code> takes <code>id</code> in the body — there is no <code>/api/admin/tests/[id]</code> route.</li>
                </ul>
            </AlertBox>
        </section>
    );
}

// ==========================================
// 4. BACKEND LOGIC
// ==========================================
function BackendLogicSection() {
    return (
        <section className="space-y-8">
            <Header title="Backend Logic & Patterns" subtitle="The two data-access patterns, audit logging, and the result-entry pipeline." />

            <Card title="Two Data-Access Patterns (and when to use which)">
                <div className="grid md:grid-cols-2 gap-4 mb-4">
                    <div className="bg-amber-50 p-4 rounded border border-amber-200">
                        <h4 className="font-bold text-amber-800 mb-2">Legacy: readDb() / writeDb()</h4>
                        <p className="text-xs text-amber-800">
                            <code>src/lib/db.ts</code> loads <em>every</em> table into one big object (parsing JSON-in-TEXT
                            columns like <code>testIds</code> on the way) and <code>writeDb()</code> writes the whole snapshot
                            back. Used by older routes (orders GET, queues, admin/tests). Convenient for cross-table reads,
                            but a full-DB rewrite per request — <strong>never add new writeDb() call sites</strong>.
                        </p>
                    </div>
                    <div className="bg-green-50 p-4 rounded border border-green-200">
                        <h4 className="font-bold text-green-800 mb-2">Modern: direct Drizzle</h4>
                        <p className="text-xs text-green-800">
                            <code>import {'{ db }'} from &apos;@/db&apos;</code> then typed <code>db.select()/insert()/update()</code>.
                            Used by all clinical-engine tables, results POST, receiving, critical values, etc. Remember to
                            <code> JSON.parse</code>/<code>JSON.stringify</code> the JSON-in-TEXT columns yourself.
                        </p>
                    </div>
                </div>
                <AlertBox type="warning" title="Mixing the patterns">
                    Both read the same SQLite file, so they interoperate — but a route that does
                    readDb → mutate → writeDb can clobber a concurrent Drizzle write. The results route was migrated off
                    this pattern for exactly that reason (v2.0.1). Prefer a single targeted Drizzle update.
                </AlertBox>
            </Card>

            <Card title="Audit Logging">
                <pre className="bg-slate-900 text-slate-300 p-4 rounded text-xs font-mono overflow-x-auto">{`// src/lib/db.ts
// First param kept for caller compatibility; audit rows ALWAYS go
// through Drizzle (callers variously pass the readDb() JSON object,
// which has no .insert).
export async function logAudit(_dbIgnored, entityType, entityId,
                               action, previousData, newData, userId) {
    await db.insert(auditLogs).values({
        id: uuidv4(), entityType, entityId, action, userId,
        timestamp: new Date().toISOString(),
        details: JSON.stringify({ previous: previousData, new: newData })
    });
}`}</pre>
                <p className="text-sm text-slate-600 mt-3">
                    Every CREATE / UPDATE / DELETE on patients, orders, tests, queues, and departments writes an audit row.
                    The first parameter is historical baggage — it is ignored. Newer routes (results, receiving) insert into
                    <code> audit_logs</code> directly with the same shape.
                </p>
            </Card>

            <Card title="The Result-Entry Pipeline (POST /api/results)">
                <ol className="list-decimal pl-5 space-y-2 text-sm text-slate-700">
                    <li><strong>Auth:</strong> resolve user from <code>auth_session</code> cookie; 401 if absent.</li>
                    <li><strong>Status resolution:</strong> <code>action</code> overrides <code>status</code> — <code>TECHNICAL_VALIDATE</code> → &apos;Technically Validated&apos;, <code>CLINICAL_VERIFY</code> → &apos;Clinically Verified&apos;.</li>
                    <li><strong>Per-test upsert:</strong> for each entry in <code>values.results</code>, find-or-insert a results row keyed on (orderId, testId). New rows also decrement reagent stock via <code>consumeReagent()</code>.</li>
                    <li><strong>Clinical engine (initial entry only):</strong> numeric values fire <code>runDeltaChecks</code>, <code>checkCriticalValues</code>, <code>evaluateReflexRules</code>; every value (incl. qualitative) fires <code>checkNotifiableConditions</code>. All four run fire-and-forget with <code>.catch</code> logging so a rule failure never blocks result entry.</li>
                    <li><strong>REPORT pseudo-row:</strong> <code>values.notes</code> upserts a row with <code>testId=&apos;REPORT&apos;</code>.</li>
                    <li><strong>Order transition:</strong> single Drizzle update sets status, <code>updatedAt</code>, <code>queueId</code> (if routed), and on CLINICAL_VERIFY also <code>status=&apos;Completed&apos;</code> + <code>completedAt</code>.</li>
                    <li><strong>E-signature:</strong> validation actions insert a <code>result_signatures</code> row capturing user, type, IP, and user agent.</li>
                    <li><strong>Audit:</strong> one audit row summarising the action and queue routing.</li>
                </ol>
            </Card>

            <Card title="Accession Number Generation">
                <p className="text-sm text-slate-700 mb-3">
                    <code>src/lib/accession.ts</code> generates sequential daily accession numbers
                    (<code>YYYY-MM-DD-XXXX</code>) server-side at order creation. Clients never supply or compute accession
                    numbers — this eliminates duplicate-ID race conditions from concurrent order entry.
                </p>
            </Card>

            <Card title="Next.js 16 Route Handler Conventions">
                <pre className="bg-slate-900 text-slate-300 p-4 rounded text-xs font-mono overflow-x-auto">{`// Dynamic params are a Promise in Next.js 16 — always await:
export async function PUT(
    request: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const { id } = await params;   // ✗ params.id directly = build error
    ...
}

// Routes that read request.url or cookies should opt out of caching:
export const dynamic = 'force-dynamic';`}</pre>
            </Card>
        </section>
    );
}

// ==========================================
// 5. CLINICAL ENGINE
// ==========================================
function ClinicalEngineSection() {
    return (
        <section className="space-y-8">
            <Header title="Clinical Decision Engine" subtitle="src/lib/clinical-engine.ts — five evaluation systems invoked automatically on result entry. All are fire-and-forget: a rule failure logs to console and never blocks the result." />

            <Card title="1. Critical Value Detection — checkCriticalValues()">
                <p className="text-sm text-slate-700 mb-3">
                    Compares each numeric result against the test definition&apos;s reference range. The canonical range shape is
                    <code> {'{ min, max, panicLow, panicHigh }'}</code>; <code>criticalLow/criticalHigh</code> are accepted as
                    legacy aliases. A breach inserts a <code>critical_value_notifications</code> row (status Pending) which:
                </p>
                <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
                    <li>appears in the <strong>Critical Values inbox</strong> (/critical-values) for acknowledgment,</li>
                    <li>is counted on the <strong>dashboard</strong> critical KPI (Pending only — acknowledged values stop alerting),</li>
                    <li>feeds the CRITICAL <strong>drill-down</strong> (/api/dashboard/details?type=CRITICAL).</li>
                </ul>
                <pre className="bg-slate-900 text-slate-300 p-4 rounded text-xs font-mono mt-3 overflow-x-auto">{`// Example: Glucose panicHigh = 500, entered value = 520
// → notification { criticalType: 'HIGH', threshold: '> 500 mg/dL',
//                  status: 'Pending', createdBy: <entering user> }
// Acknowledgment (POST /api/critical-values/[id]/ack) records the
// notified clinician, method (phone/fax/in-person), and read-back notes
// in critical_value_acknowledgments — the ISO 15189 paper trail.`}</pre>
            </Card>

            <Card title="2. Delta Checks — runDeltaChecks()">
                <p className="text-sm text-slate-700 mb-3">
                    Detects implausible changes between consecutive results for the same patient + test (possible specimen
                    mix-up or pre-analytical error). The engine looks back through the patient&apos;s 5 most recent other orders
                    for the previous value of the same test, then evaluates every enabled rule:
                </p>
                <table className="w-full text-xs text-left mb-3">
                    <thead className="bg-slate-50 border-b"><tr><th className="p-2">Rule field</th><th className="p-2">Effect</th></tr></thead>
                    <tbody className="divide-y">
                        <tr><td className="p-2 font-mono">deltaType: &apos;percent&apos;</td><td className="p-2">flag when |Δ%| ≥ threshold</td></tr>
                        <tr><td className="p-2 font-mono">deltaType: &apos;absolute&apos;</td><td className="p-2">flag when |Δ| ≥ threshold</td></tr>
                        <tr><td className="p-2 font-mono">direction</td><td className="p-2">&apos;any&apos; | &apos;increase&apos; | &apos;decrease&apos; — gate on change direction</td></tr>
                    </tbody>
                </table>
                <p className="text-xs text-slate-500">Violations land in <code>delta_check_flags</code> with both values and both computed deltas. Configure rules at /admin/delta-checks; review flags via /api/delta-checks/flags.</p>
            </Card>

            <Card title="3. Reflex Testing — evaluateReflexRules()">
                <p className="text-sm text-slate-700 mb-3">
                    Conditional add-on testing. When the trigger test&apos;s value satisfies
                    <code> triggerCondition {'{ operator, value }'}</code> (operators: &gt; &lt; &gt;= &lt;= ==), the engine:
                </p>
                <ol className="list-decimal pl-5 text-sm text-slate-700 space-y-1">
                    <li>records a <code>reflex_activations</code> row (deduplicated per order+rule),</li>
                    <li><strong>appends <code>addTestId</code> to the order&apos;s <code>testIds</code></strong> — the reflexed test immediately appears in the results-entry grid for that order.</li>
                </ol>
                <pre className="bg-slate-900 text-slate-300 p-4 rounded text-xs font-mono mt-3 overflow-x-auto">{`// Example rule: GLU > 400 → add CREAT
// Order had testIds ["test-glu"]; after a 450 result:
//   testIds = ["test-glu", "test-creat"]   (verified in QA)`}</pre>
            </Card>

            <Card title="4. Notifiable Condition Surveillance — checkNotifiableConditions()">
                <p className="text-sm text-slate-700 mb-3">
                    Public-health reporting hook. Runs on <em>every</em> result (numeric or qualitative). If the resulted
                    test id appears in any active <code>notifiable_conditions.testIds</code> array, a Pending
                    <code> epidemiology_notifications</code> row is created (deduplicated per order+condition). The
                    /epidemiology page then drives the human workflow: Pending → Reviewed → Submitted → Closed, restricted
                    to manager/admin.
                </p>
            </Card>

            <Card title="5. Demographic Reference Ranges — getDemographicRefRange()">
                <p className="text-sm text-slate-700 mb-3">
                    Looks up age/gender/pregnancy-specific ranges from <code>demographic_reference_ranges</code>, scoring
                    candidates by specificity (exact age band + gender + trimester beats gender-only, which beats
                    all-comers). Falls back to the test definition&apos;s default range when no demographic row matches.
                    Configured at /admin/demographic-ranges.
                </p>
            </Card>

            <Card title="6. Calculated Tests — computeCalculatedTests()">
                <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 border-b"><tr><th className="p-2">formulaType</th><th className="p-2">Formula</th><th className="p-2">Inputs</th></tr></thead>
                    <tbody className="divide-y">
                        <tr><td className="p-2 font-mono">ldl_friedewald</td><td className="p-2">LDL = TC − HDL − TG/5</td><td className="p-2 font-mono">totalCholesterol, hdl, triglycerides</td></tr>
                        <tr><td className="p-2 font-mono">anion_gap</td><td className="p-2">AG = Na − (Cl + HCO₃)</td><td className="p-2 font-mono">sodium, chloride, bicarbonate</td></tr>
                        <tr><td className="p-2 font-mono">a_g_ratio</td><td className="p-2">A/G = Alb / (TP − Alb)</td><td className="p-2 font-mono">albumin, totalProtein</td></tr>
                        <tr><td className="p-2 font-mono">egfr_ckd_epi</td><td className="p-2">CKD-EPI 2021 (age, sex, creatinine)</td><td className="p-2 font-mono">creatinine + patient demographics</td></tr>
                    </tbody>
                </table>
                <p className="text-xs text-slate-500 mt-3">
                    Exposed via GET /api/calculated-tests/compute. Note: no UI consumes this endpoint yet — it is available
                    for worksheet integration.
                </p>
            </Card>

            <AlertBox type="warning" title="When the engine does NOT run">
                The engine only fires on <strong>initial result entry</strong> (no <code>action</code>, or a plain
                <code> status</code>). Re-validation passes (TECHNICAL_VALIDATE / CLINICAL_VERIFY) deliberately skip it so
                that signing off results cannot re-trigger notifications or reflex additions.
            </AlertBox>
        </section>
    );
}

// ==========================================
// 6. WORKFLOWS
// ==========================================
function WorkflowsSection() {
    return (
        <section className="space-y-8">
            <Header title="End-to-End Workflows" subtitle="How a specimen travels through the system, and which statuses gate each step." />

            <Card title="Order Status Lifecycle">
                <div className="text-xs font-mono space-y-2">
                    <div className="bg-slate-100 p-2 rounded border border-slate-200">Preliminary <span className="text-slate-400">— created at accessioning (POST /api/orders)</span></div>
                    <div className="flex justify-center"><ArrowDown /></div>
                    <div className="bg-blue-50 p-2 rounded border border-blue-200">Pending Validation <span className="text-slate-400">— results entered (POST /api/results, status)</span></div>
                    <div className="flex justify-center"><ArrowDown /></div>
                    <div className="bg-purple-50 p-2 rounded border border-purple-200">Technically Validated <span className="text-slate-400">— action: TECHNICAL_VALIDATE (+ technical e-signature)</span></div>
                    <div className="flex justify-center"><ArrowDown /></div>
                    <div className="bg-green-50 p-2 rounded border border-green-200">Completed <span className="text-slate-400">— action: CLINICAL_VERIFY (+ clinical e-signature, completedAt)</span></div>
                </div>
                <p className="text-xs text-slate-500 mt-3">The dashboard counts everything ≠ &apos;Completed&apos; as pending. TAT = completedAt − timestamp.</p>
            </Card>

            <Card title="The Happy Path (verified end-to-end in QA)">
                <ol className="list-decimal pl-5 space-y-2 text-sm text-slate-700">
                    <li><strong>Accessioning</strong> (/accessioning): search or register patient → select tests → record samples → POST /api/orders creates the order (Preliminary), one specimen row per sample, and an audit entry. Accession number comes back server-generated.</li>
                    <li><strong>Receiving</strong> (/receiving): pending list = specimens with no receiving record, joined with order + patient. Accept (Acceptable), flag for recollection (Marginal), or reject with reason. Updates specimen status.</li>
                    <li><strong>Result entry</strong> (/results): select order (record lock auto-acquired via /api/locks), enter values per test, submit. Clinical engine fires per value: critical glucose 520 → notification; 77% delta → flag; GLU&gt;400 → reflex CREAT appended; notifiable test → epi notification.</li>
                    <li><strong>Critical value handling</strong> (/critical-values): pending notifications listed with patient + accession; acknowledging records clinician, method, and read-back notes.</li>
                    <li><strong>Technical validation → clinical verification</strong> (/results): two-stage sign-off; the second stage completes the order and stamps both e-signatures.</li>
                    <li><strong>Reporting</strong> (/reports): completed orders listed; report shows branded header (lab settings), flagged results (H/L/C-HIGH/C-LOW from the canonical reference-range shape), signature block, and prints via a dedicated window. /reports/cumulative renders the longitudinal flowsheet.</li>
                </ol>
            </Card>

            <Card title="Record Locking (Concurrent Editing)">
                <p className="text-sm text-slate-700 mb-2">
                    Opening an order in results entry auto-acquires a checkout lock (<code>record_locks</code> via
                    /api/locks) with a heartbeat. A second user sees the lock holder and is read-only. Admins can
                    force-check-in with a mandatory reason (audited).
                </p>
            </Card>

            <Card title="Supporting Workflows">
                <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 border-b"><tr><th className="p-2">Workflow</th><th className="p-2">Pages</th><th className="p-2">Flow</th></tr></thead>
                    <tbody className="divide-y">
                        <tr><td className="p-2 font-bold">Phlebotomy</td><td className="p-2 font-mono">/phlebotomy</td><td className="p-2">Schedule draw (patient, ward, time, collection type) → Scheduled → Collected/No-show transitions</td></tr>
                        <tr><td className="p-2 font-bold">Epidemiology</td><td className="p-2 font-mono">/epidemiology</td><td className="p-2">Auto-detected Pending → Reviewed → Submitted → Closed (manager/admin)</td></tr>
                        <tr><td className="p-2 font-bold">Specimen retention</td><td className="p-2 font-mono">/admin/retention</td><td className="p-2">Policies per specimen type (days, temperature, disposal method) → batch disposal with audit via /api/retention/dispose</td></tr>
                        <tr><td className="p-2 font-bold">TAT monitoring</td><td className="p-2 font-mono">/dashboard/tat, /admin/tat-thresholds</td><td className="p-2">Thresholds (global/department/test scope, warning/breach hours) → breaches surfaced on TAT dashboard</td></tr>
                        <tr><td className="p-2 font-bold">Work queues</td><td className="p-2 font-mono">/queues, /admin/queues</td><td className="p-2">Department + role scoped queues; validation routing sets order.queueId; queue page shows enriched orders with patient names</td></tr>
                        <tr><td className="p-2 font-bold">Competency</td><td className="p-2 font-mono">/admin/competency</td><td className="p-2">Per-user assessments with expiry tracking (expiring-soon highlighting)</td></tr>
                    </tbody>
                </table>
            </Card>
        </section>
    );
}

// ==========================================
// 7. SECURITY & AUTH
// ==========================================
function SecuritySection() {
    return (
        <section className="space-y-8">
            <Header title="Security & Authentication" subtitle="Dual-cookie sessions, password hashing, RBAC, and the audit trail." />

            <Card title="The Dual-Cookie Session Model">
                <p className="text-sm text-slate-700 mb-3">
                    Login (<code>POST /api/auth/login</code>) sets <strong>two</strong> httpOnly cookies with identical
                    options (<code>sameSite: strict</code>, <code>secure</code> in production, 24h maxAge):
                </p>
                <table className="w-full text-xs text-left mb-3">
                    <thead className="bg-slate-50 border-b"><tr><th className="p-2">Cookie</th><th className="p-2">Contents</th><th className="p-2">Consumed by</th></tr></thead>
                    <tbody className="divide-y">
                        <tr><td className="p-2 font-mono font-bold">auth_token</td><td className="p-2">Session UUID → looked up in the <code>sessions</code> table (with expiry check)</td><td className="p-2">Newer routes (orders, queues, receiving, admin/tests)</td></tr>
                        <tr><td className="p-2 font-mono font-bold">auth_session</td><td className="p-2">JSON-encoded user object (sans password)</td><td className="p-2">~46 legacy routes that parse it directly</td></tr>
                    </tbody>
                </table>
                <AlertBox type="warning" title="History lesson">
                    At one point login set only <code>auth_token</code> and deleted <code>auth_session</code> — every legacy
                    route silently returned 401 and the app looked like a dummy interface. Both cookies are now always set,
                    and logout deletes both plus the sessions row. If you write a new route, use the unified helper below
                    instead of reading cookies directly.
                </AlertBox>
                <pre className="bg-slate-900 text-slate-300 p-4 rounded text-xs font-mono overflow-x-auto">{`// src/lib/auth.ts — preferred for all new routes
import { getAuthUser, requireRole } from '@/lib/auth';

const user = await getAuthUser();   // tries auth_token → sessions,
                                    // falls back to auth_session JSON
if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
if (!requireRole(user, ['admin', 'manager'])) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
}`}</pre>
            </Card>

            <Card title="Password Storage">
                <ul className="list-disc pl-5 text-sm text-slate-700 space-y-2">
                    <li>Passwords are bcrypt-hashed (cost 12) via <code>bcryptjs</code>.</li>
                    <li><strong>Transparent upgrade:</strong> legacy cleartext passwords (pre-hashing era) still authenticate once — on successful login the password is immediately re-stored as a bcrypt hash.</li>
                    <li>Hash detection is by prefix (<code>$2…</code>); <code>src/scripts/hash-passwords.ts</code> can batch-upgrade.</li>
                    <li>User objects returned by APIs always strip the password field.</li>
                </ul>
            </Card>

            <Card title="RBAC Matrix">
                <table className="w-full text-sm">
                    <thead className="bg-slate-100"><tr><th className="p-2 text-left">Capability</th><th className="p-2">admin</th><th className="p-2">manager</th><th className="p-2">scientist</th><th className="p-2">medic</th><th className="p-2">clerk</th></tr></thead>
                    <tbody>
                        <tr className="border-b"><td className="p-2">View dashboards / worklists</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-green-600">✓</td></tr>
                        <tr className="border-b"><td className="p-2">Accession orders</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-red-600">✗</td><td className="p-2 text-center text-green-600">✓</td></tr>
                        <tr className="border-b"><td className="p-2">Enter results</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-amber-600">view</td><td className="p-2 text-center text-red-600">✗</td></tr>
                        <tr className="border-b"><td className="p-2">Clinical verification (release)</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-red-600">✗</td><td className="p-2 text-center text-red-600">✗</td><td className="p-2 text-center text-red-600">✗</td></tr>
                        <tr className="border-b"><td className="p-2">Rule / queue / config CRUD</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-red-600">✗ (403)</td><td className="p-2 text-center text-red-600">✗ (403)</td><td className="p-2 text-center text-red-600">✗ (403)</td></tr>
                        <tr><td className="p-2">User management / backup / restore</td><td className="p-2 text-center text-green-600">✓</td><td className="p-2 text-center text-red-600">✗</td><td className="p-2 text-center text-red-600">✗</td><td className="p-2 text-center text-red-600">✗</td><td className="p-2 text-center text-red-600">✗</td></tr>
                    </tbody>
                </table>
                <p className="text-xs text-slate-500 mt-2">Managers are additionally scoped to their own department for queue management. RBAC is enforced server-side in each route (verified by QA: clerk receives 403 on config mutations).</p>
            </Card>

            <Card title="Compliance Surface">
                <ul className="list-disc pl-5 text-sm text-slate-700 space-y-2">
                    <li><strong>Audit trail:</strong> immutable <code>audit_logs</code> rows for all entity mutations, with before/after snapshots (ISO 15189 §8.4).</li>
                    <li><strong>E-signatures:</strong> <code>result_signatures</code> captures who/when/IP/user-agent for both validation stages (21 CFR Part 11 style non-repudiation).</li>
                    <li><strong>Critical value read-back:</strong> acknowledgments store notified clinician + method + notes (ISO 15189 §7.4.1.6).</li>
                    <li><strong>Backups:</strong> AES-256-GCM encrypted snapshots via /api/admin/backup; restore requires the passphrase.</li>
                    <li><strong>Record locks:</strong> checkout model prevents concurrent edits; force-check-in is admin-only and requires a reason.</li>
                </ul>
            </Card>
        </section>
    );
}

// ==========================================
// 8. DESIGN SYSTEM
// ==========================================
function DesignSystemSection() {
    return (
        <section className="space-y-8">
            <Header title="Design System" subtitle="Tailwind + CSS-variable theming, colour semantics, and layout conventions." />

            <Card title="Runtime Theming">
                <p className="text-sm text-slate-700 mb-3">
                    Tailwind is configured to resolve <code>primary-*</code> shades from CSS variables, so themes switch at
                    runtime without rebuilding. Five schemes ship by default; the active theme is a class on the root
                    element, persisted in settings:
                </p>
                <div className="grid grid-cols-5 gap-2 mb-3">
                    <div className="bg-blue-600 text-white p-2 rounded text-center text-xs">Clinical Blue</div>
                    <div className="bg-emerald-600 text-white p-2 rounded text-center text-xs">Bio-Emerald</div>
                    <div className="bg-rose-600 text-white p-2 rounded text-center text-xs">Crimson</div>
                    <div className="bg-indigo-600 text-white p-2 rounded text-center text-xs">Deep Indigo</div>
                    <div className="bg-slate-900 text-white p-2 rounded text-center text-xs">High Contrast</div>
                </div>
                <pre className="bg-slate-900 text-green-400 p-2 rounded text-xs">{`.theme-rose { --primary-500: #f43f5e; --primary-600: #e11d48; ... }
/* Dark mode: full dark UI for microscopy / low-light benches */`}</pre>
            </Card>

            <Card title="Colour Semantics (Clinical)">
                <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 border-b"><tr><th className="p-2">Meaning</th><th className="p-2">Classes</th><th className="p-2">Used for</th></tr></thead>
                    <tbody className="divide-y">
                        <tr><td className="p-2 font-bold text-red-700">Critical</td><td className="p-2 font-mono">text-red-700 / bg-red-100, font-bold</td><td className="p-2">C-HIGH/C-LOW flags, STAT badges, panic ranges, rejected specimens</td></tr>
                        <tr><td className="p-2 font-bold text-amber-700">Abnormal / warning</td><td className="p-2 font-mono">text-amber-700 / bg-amber-100</td><td className="p-2">H/L flags, marginal specimens, TAT warnings, expiring competencies</td></tr>
                        <tr><td className="p-2 font-bold text-green-700">Accepted / complete</td><td className="p-2 font-mono">text-green-700 / bg-green-100</td><td className="p-2">Accepted specimens, Completed status, passing QC</td></tr>
                        <tr><td className="p-2 font-bold text-blue-700">Active / informational</td><td className="p-2 font-mono">text-blue-700 / bg-blue-100</td><td className="p-2">In-progress states, selected queue items, counts</td></tr>
                    </tbody>
                </table>
            </Card>

            <Card title="Layout Conventions">
                <ul className="list-disc pl-5 text-sm text-slate-700 space-y-2">
                    <li><strong>Master-detail:</strong> list panel (w-64 to w-80) + flex-1 detail area, both with independent scroll (<code>h-[calc(100vh-…)]</code> + <code>overflow-y-auto</code>). Used by queues, reports, results, docs.</li>
                    <li><strong>Print isolation:</strong> reports render into a ref&apos;d div; printing opens a new window with serif/Times styles injected — screen styles never leak into the PDF.</li>
                    <li><strong>Forms:</strong> <code>.input-field</code> utility class for consistent inputs; inline validation messages, never browser alerts for validation (alerts are reserved for destructive confirmations).</li>
                    <li><strong>Charts:</strong> Recharts inside a fixed-height container (<code>h-56</code>/<code>h-64</code>) wrapping <code>ResponsiveContainer width=&quot;100%&quot; height=&quot;100%&quot;</code> — a parent without explicit height renders a 0-size chart.</li>
                </ul>
            </Card>
        </section>
    );
}

// ==========================================
// 9. COMPONENT LIBRARY
// ==========================================
function ComponentsSection() {
    return (
        <section className="space-y-8">
            <Header title="Component Library" subtitle="Shared components under src/components. Import UI primitives from @/components/ui/*." />

            <Card title="UI Primitives (src/components/ui)">
                <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 border-b"><tr><th className="p-2">Component</th><th className="p-2">Props (key)</th><th className="p-2">Notes</th></tr></thead>
                    <tbody className="divide-y">
                        <tr><td className="p-2 font-mono font-bold">Card</td><td className="p-2 font-mono">title?, className?, children</td><td className="p-2">Standard white panel with optional header — the workhorse container</td></tr>
                        <tr><td className="p-2 font-mono font-bold">Badge / StatusBadge</td><td className="p-2 font-mono">status</td><td className="p-2">StatusBadge maps order statuses to semantic colours automatically</td></tr>
                        <tr><td className="p-2 font-mono font-bold">Table</td><td className="p-2 font-mono">columns, data</td><td className="p-2">Declarative table for dashboard drill-downs</td></tr>
                        <tr><td className="p-2 font-mono font-bold">button / input / label / alert</td><td className="p-2 font-mono">standard HTML props</td><td className="p-2">shadcn-style primitives</td></tr>
                        <tr><td className="p-2 font-mono font-bold">RichTextEditor</td><td className="p-2 font-mono">value, onChange</td><td className="p-2">Used for document editing</td></tr>
                    </tbody>
                </table>
            </Card>

            <Card title="Domain Components">
                <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 border-b"><tr><th className="p-2">Component</th><th className="p-2">Purpose</th></tr></thead>
                    <tbody className="divide-y">
                        <tr><td className="p-2 font-mono font-bold">Sidebar</td><td className="p-2">Role-aware navigation. Workspace / Samples & Tracking / Clinical Analysis / Admin groups; admin links render only for admin role. Add new pages here AND as a route.</td></tr>
                        <tr><td className="p-2 font-mono font-bold">reports/PatientReport</td><td className="p-2">Print layout for single-order patient reports (used with react-to-print)</td></tr>
                        <tr><td className="p-2 font-mono font-bold">reports/CoaReport</td><td className="p-2">Certificate of Analysis layout for manufacturing QC</td></tr>
                        <tr><td className="p-2 font-mono font-bold">AlertBanner</td><td className="p-2">System-wide alert strip fed by /api/alerts/active</td></tr>
                        <tr><td className="p-2 font-mono font-bold">AliquotManager</td><td className="p-2">Specimen aliquoting UI (POST /api/samples/aliquot)</td></tr>
                        <tr><td className="p-2 font-mono font-bold">CoCTimeline</td><td className="p-2">Chain-of-custody event timeline (GET /api/coc)</td></tr>
                    </tbody>
                </table>
            </Card>

            <Card title="Context">
                <pre className="bg-slate-900 text-slate-300 p-4 rounded text-xs font-mono overflow-x-auto">{`// src/context/AuthContext.tsx
const { user } = useAuth();
// user: { id, username, role, name, department } | null
// Hydrated from GET /api/auth/me on mount.
// Gate UI affordances on user.role — but remember the SERVER
// enforces RBAC; client checks are cosmetic only.`}</pre>
            </Card>

            <Card title="Adding a New Feature Page (checklist)">
                <ol className="list-decimal pl-5 text-sm text-slate-700 space-y-1">
                    <li>Table(s) in <code>src/db/schema.ts</code> + CREATE TABLE in <code>src/scripts/apply-new-tables.js</code> (run it once).</li>
                    <li>API route under <code>src/app/api/&lt;name&gt;/route.ts</code> — use <code>getAuthUser()</code>, enforce roles, await <code>params</code>.</li>
                    <li>Page under <code>src/app/&lt;name&gt;/page.tsx</code> (&apos;use client&apos;, fetch in useEffect, guard non-array responses).</li>
                    <li>Sidebar entry in <code>src/components/Sidebar.tsx</code> with a lucide icon.</li>
                    <li>If results should trigger it automatically → hook into <code>src/lib/clinical-engine.ts</code> and call from the results POST.</li>
                    <li><code>npx tsc --noEmit</code> + <code>npm run build</code> must both pass clean.</li>
                </ol>
            </Card>
        </section>
    );
}

// ==========================================
// 10. OPS & DEPLOYMENT
// ==========================================
function DeploymentSection() {
    return (
        <section className="space-y-8">
            <Header title="Operations Manual" subtitle="Building, deploying, migrating, and maintaining the LIS." />

            <div className="grid grid-cols-1 gap-6">
                <Card title="Commands">
                    <pre className="bg-slate-900 text-green-400 p-3 rounded text-xs">{`npm run dev      # Development server (hot reload) on :3000
npm run build    # Production build — must pass with 0 errors
npm run start    # Serve the production build
npx tsc --noEmit # Type check without building
npm run lint     # ESLint`}</pre>
                </Card>

                <Card title="Database Migrations">
                    <div className="space-y-3 text-sm text-slate-700">
                        <p>
                            Schema lives in <code>src/db/schema.ts</code>; the live database is <code>sqlite_v2.db</code> in
                            the project root. Two migration paths exist:
                        </p>
                        <ul className="list-disc pl-5 space-y-1">
                            <li><strong>drizzle-kit:</strong> <code>npx drizzle-kit generate</code> + <code>migrate</code> — but it can attempt to re-run historical migrations on databases that predate the migrations table.</li>
                            <li><strong>Direct script (preferred for additive changes):</strong> <code>node src/scripts/apply-new-tables.js</code> uses <code>CREATE TABLE IF NOT EXISTS</code> — idempotent and safe to re-run.</li>
                        </ul>
                        <AlertBox type="warning" title="Path bug — already fixed, stay alert">
                            The migration script once resolved its DB path one directory too high and silently created all 24
                            new tables in a stray <code>sqlite_v2.db</code> in the project&apos;s <em>parent</em> folder. Every new
                            module then threw &quot;no such table&quot; at runtime. The path is now <code>__dirname/../../sqlite_v2.db</code>.
                            After any migration, verify with: <code>SELECT name FROM sqlite_master WHERE type=&apos;table&apos;</code>.
                        </AlertBox>
                    </div>
                </Card>

                <Card title="Backup & Disaster Recovery">
                    <div className="space-y-4">
                        <AlertBox type="warning" title="Backup target">
                            The entire system state is <code>sqlite_v2.db</code> (single file). Back it up at least hourly.
                            <strong> /api/admin/backup</strong> produces an AES-256-GCM encrypted snapshot; restoring requires
                            the passphrase via the admin Recovery UI.
                        </AlertBox>
                        <div className="bg-slate-50 p-4 rounded border border-slate-200">
                            <h4 className="font-bold text-sm mb-2">Restoration Procedure (RTO &lt; 15 min)</h4>
                            <ol className="list-decimal pl-5 text-sm space-y-1">
                                <li>Stop the application service.</li>
                                <li>Navigate to System → Recovery (or replace <code>sqlite_v2.db</code> from a file backup).</li>
                                <li>Upload the <code>.enc</code> backup + passphrase; the system decrypts and swaps the DB.</li>
                                <li>Restart and verify with a login + dashboard load.</li>
                            </ol>
                        </div>
                    </div>
                </Card>

                <Card title="Hybrid Development Workflow">
                    <div className="grid md:grid-cols-2 gap-4">
                        <div className="bg-blue-50 p-4 rounded border border-blue-200">
                            <h4 className="font-bold text-blue-800 mb-2 flex items-center gap-2"><Code className="w-4 h-4" /> Local Development</h4>
                            <code className="block bg-white px-2 py-1 rounded border mb-2 text-xs font-mono">npm run dev</code>
                            <ul className="text-xs text-blue-700 list-disc pl-4 space-y-1">
                                <li>Hot reloading; writes to local <strong>sqlite_v2.db</strong></li>
                                <li>Default credentials: admin / admin123</li>
                            </ul>
                        </div>
                        <div className="bg-slate-100 p-4 rounded border border-slate-200">
                            <h4 className="font-bold text-slate-800 mb-2 flex items-center gap-2"><Server className="w-4 h-4" /> Production / Integration</h4>
                            <code className="block bg-white px-2 py-1 rounded border mb-2 text-xs font-mono">docker-compose up --build</code>
                            <ul className="text-xs text-slate-700 list-disc pl-4 space-y-1">
                                <li>Full stack (app + instrument server)</li>
                                <li>Mounts the SAME <strong>sqlite_v2.db</strong> volume</li>
                            </ul>
                        </div>
                    </div>
                </Card>

                <Card title="Seed & Utility Scripts (src/scripts)">
                    <table className="w-full text-xs text-left">
                        <thead className="bg-slate-50 border-b"><tr><th className="p-2">Script</th><th className="p-2">Purpose</th></tr></thead>
                        <tbody className="divide-y">
                            <tr><td className="p-2 font-mono">apply-new-tables.js</td><td className="p-2">Idempotent CREATE TABLE for the 24 clinical-feature tables</td></tr>
                            <tr><td className="p-2 font-mono">hash-passwords.ts</td><td className="p-2">Batch-upgrade any remaining cleartext passwords to bcrypt</td></tr>
                            <tr><td className="p-2 font-mono">seed-from-json.ts / migrate-json.ts</td><td className="p-2">One-time import from the legacy db.json era</td></tr>
                            <tr><td className="p-2 font-mono">verify-crypto.ts</td><td className="p-2">Self-test for the AES-256-GCM backup encryption</td></tr>
                        </tbody>
                    </table>
                </Card>
            </div>
        </section>
    );
}

// ==========================================
// 11. TROUBLESHOOTING
// ==========================================
function TroubleshootingSection() {
    return (
        <section className="space-y-8">
            <Header title="Troubleshooting Guide" subtitle="Every entry below is a real failure encountered in this codebase, with its verified fix." />

            <Card title="Known Failure Modes">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 border-b"><tr><th className="p-3">Symptom</th><th className="p-3">Cause</th><th className="p-3">Fix</th></tr></thead>
                    <tbody className="divide-y">
                        <tr>
                            <td className="p-3 font-mono text-red-600 text-xs">SqliteError: no such table</td>
                            <td className="p-3 text-xs">Migration ran against the wrong DB file (path resolution), or apply-new-tables.js was never run on this checkout.</td>
                            <td className="p-3 text-xs">Run <code>node src/scripts/apply-new-tables.js</code>; verify tables with sqlite_master; check for a stray sqlite_v2.db in the parent directory.</td>
                        </tr>
                        <tr>
                            <td className="p-3 font-mono text-red-600 text-xs">Failed to log audit: db.insert is not a function</td>
                            <td className="p-3 text-xs">A caller passed the readDb() JSON snapshot to logAudit, which used to call .insert on it.</td>
                            <td className="p-3 text-xs">Fixed: logAudit ignores its first param and always writes via Drizzle. If you see this again, someone re-introduced a local logAudit.</td>
                        </tr>
                        <tr>
                            <td className="p-3 font-mono text-red-600 text-xs">All writes return 401 while logged in</td>
                            <td className="p-3 text-xs">One of the two auth cookies missing — login must set BOTH auth_token and auth_session.</td>
                            <td className="p-3 text-xs">Check login route sets both; new routes should use getAuthUser() from src/lib/auth.ts which tries both.</td>
                        </tr>
                        <tr>
                            <td className="p-3 font-mono text-red-600 text-xs">Dashboard counts stuck at 0</td>
                            <td className="p-3 text-xs">Status string casing (&apos;completed&apos; vs &apos;Completed&apos;) or using the non-existent orders.createdAt field.</td>
                            <td className="p-3 text-xs">Statuses are capitalised; the order-creation time column is <code>timestamp</code>.</td>
                        </tr>
                        <tr>
                            <td className="p-3 font-mono text-red-600 text-xs">Critical values / report flags never fire</td>
                            <td className="p-3 text-xs">Code reading criticalLow/criticalHigh or low/high from referenceRange.</td>
                            <td className="p-3 text-xs">Canonical shape is {'{ min, max, panicLow, panicHigh }'} — see Database tab.</td>
                        </tr>
                        <tr>
                            <td className="p-3 font-mono text-red-600 text-xs">Type error: params.id on dynamic route</td>
                            <td className="p-3 text-xs">Next.js 16 makes params a Promise.</td>
                            <td className="p-3 text-xs">{`{ params }: { params: Promise<{ id: string }> }`} then <code>const {'{ id }'} = await params</code>.</td>
                        </tr>
                        <tr>
                            <td className="p-3 font-mono text-red-600 text-xs">Recharts: width(-1)/height(-1) warning</td>
                            <td className="p-3 text-xs">ResponsiveContainer parent has no explicit height, or viewport collapsed the grid column to zero.</td>
                            <td className="p-3 text-xs">Wrap charts in a fixed-height div (h-56/h-64). The warning at very narrow viewports is benign.</td>
                        </tr>
                        <tr>
                            <td className="p-3 font-mono text-red-600 text-xs">Invalid source map (dev log spam)</td>
                            <td className="p-3 text-xs">Next.js dev-mode noise on Windows.</td>
                            <td className="p-3 text-xs">Harmless; absent in production builds. Ignore.</td>
                        </tr>
                        <tr>
                            <td className="p-3 font-mono text-red-600 text-xs">Hydration mismatch</td>
                            <td className="p-3 text-xs">Server/client HTML divergence — usually Date rendering.</td>
                            <td className="p-3 text-xs">Render dates in useEffect, or suppressHydrationWarning on the node.</td>
                        </tr>
                        <tr>
                            <td className="p-3 font-mono text-red-600 text-xs">drizzle-kit migrate re-runs old migrations</td>
                            <td className="p-3 text-xs">__drizzle_migrations out of sync with applied schema.</td>
                            <td className="p-3 text-xs">Use the idempotent apply-new-tables.js path for additive changes instead.</td>
                        </tr>
                    </tbody>
                </table>
            </Card>

            <Card title="Diagnostic Quick Reference">
                <pre className="bg-slate-900 text-slate-300 p-4 rounded text-xs font-mono overflow-x-auto">{`# What tables actually exist?
node -e "const D=require('better-sqlite3');const db=new D('sqlite_v2.db');
console.log(db.prepare(\\"SELECT name FROM sqlite_master WHERE type='table'\\").all())"

# Is the session valid?
curl -b cookies.txt http://localhost:3000/api/auth/me

# Did the clinical engine fire?
curl -b cookies.txt "http://localhost:3000/api/critical-values?status=Pending"
curl -b cookies.txt http://localhost:3000/api/delta-checks/flags

# Full health pass
npx tsc --noEmit && npm run build`}</pre>
            </Card>
        </section>
    );
}

// ==========================================
// 12. SYSTEM BLUEPRINT
// ==========================================
function BlueprintSection() {
    return (
        <section className="space-y-8">
            <Header title="System Blueprint" subtitle="Complete reference for rebuilding Dx LIS from scratch." />
            <Card title="Technology Stack">
                <table className="w-full text-sm">
                    <thead className="bg-slate-100"><tr><th className="p-2 text-left">Category</th><th className="p-2 text-left">Tech</th><th className="p-2 text-left">Version</th></tr></thead>
                    <tbody>
                        <tr className="border-b"><td className="p-2">Framework</td><td className="p-2 font-mono">Next.js (App Router)</td><td className="p-2">16.0.10</td></tr>
                        <tr className="border-b"><td className="p-2">UI</td><td className="p-2 font-mono">React + Tailwind CSS</td><td className="p-2">19.2.1 / 3.4.1</td></tr>
                        <tr className="border-b"><td className="p-2">Database</td><td className="p-2 font-mono">SQLite (better-sqlite3) + Drizzle ORM</td><td className="p-2">12.5.0 / 0.45.1</td></tr>
                        <tr className="border-b"><td className="p-2">Charts</td><td className="p-2 font-mono">Recharts</td><td className="p-2">3.6.0</td></tr>
                        <tr className="border-b"><td className="p-2">Auth hashing</td><td className="p-2 font-mono">bcryptjs</td><td className="p-2">3.0.3</td></tr>
                        <tr><td className="p-2">Icons</td><td className="p-2 font-mono">lucide-react</td><td className="p-2">latest</td></tr>
                    </tbody>
                </table>
            </Card>
            <Card title="Scale Snapshot">
                <div className="grid grid-cols-4 gap-3 text-center">
                    <div className="bg-blue-50 p-4 rounded border border-blue-200"><div className="text-2xl font-bold text-blue-800">141</div><div className="text-xs text-blue-700">Build routes</div></div>
                    <div className="bg-green-50 p-4 rounded border border-green-200"><div className="text-2xl font-bold text-green-800">~100</div><div className="text-xs text-green-700">API endpoints</div></div>
                    <div className="bg-purple-50 p-4 rounded border border-purple-200"><div className="text-2xl font-bold text-purple-800">59</div><div className="text-xs text-purple-700">Database tables</div></div>
                    <div className="bg-amber-50 p-4 rounded border border-amber-200"><div className="text-2xl font-bold text-amber-800">60+</div><div className="text-xs text-amber-700">UI pages</div></div>
                </div>
            </Card>
            <Card title="Feature Modules">
                <div className="grid md:grid-cols-3 gap-4">
                    <div className="bg-blue-50 p-3 rounded border border-blue-200">
                        <h4 className="font-bold text-blue-800 mb-2">Core Workflow</h4>
                        <p className="text-xs text-blue-700">Accessioning, specimen receiving, phlebotomy scheduling, results entry, two-stage validation, work queues, record locking, reporting (single + cumulative)</p>
                    </div>
                    <div className="bg-red-50 p-3 rounded border border-red-200">
                        <h4 className="font-bold text-red-800 mb-2">Clinical Engine</h4>
                        <p className="text-xs text-red-700">Critical values + acknowledgment, delta checks, reflex testing, notifiable-condition surveillance, demographic ranges, calculated tests (LDL, anion gap, A/G, eGFR)</p>
                    </div>
                    <div className="bg-purple-50 p-3 rounded border border-purple-200">
                        <h4 className="font-bold text-purple-800 mb-2">Compliance</h4>
                        <p className="text-xs text-purple-700">E-signatures, audit trail, TAT thresholds + breaches, competency tracking, retention + disposal, LOINC catalogue, requesters, distribution rules, encrypted backup</p>
                    </div>
                    <div className="bg-green-50 p-3 rounded border border-green-200">
                        <h4 className="font-bold text-green-800 mb-2">Departments</h4>
                        <p className="text-xs text-green-700">Microbiology (cultures, antibiotics), histology (blocks, slides), manufacturing (recipes, CoA), QC (materials, runs, Westgard flags)</p>
                    </div>
                    <div className="bg-amber-50 p-3 rounded border border-amber-200">
                        <h4 className="font-bold text-amber-800 mb-2">Operations</h4>
                        <p className="text-xs text-amber-700">Inventory + reagent consumption, equipment logs, billing/invoices, storage management, tracking, chain of custody, worksheets, workstations</p>
                    </div>
                    <div className="bg-slate-100 p-3 rounded border border-slate-300">
                        <h4 className="font-bold text-slate-800 mb-2">Integration</h4>
                        <p className="text-xs text-slate-700">Analyzer middleware ingest, FHIR DiagnosticReport export, ZPL labels, email delivery queue, KPI analytics</p>
                    </div>
                </div>
            </Card>
            <Card title="Default Users (development seed)">
                <div className="grid grid-cols-3 gap-2 text-sm font-mono">
                    <div className="bg-slate-100 p-2 rounded">admin / admin123 <span className="text-xs text-slate-400 block">admin</span></div>
                    <div className="bg-slate-100 p-2 rounded">manager / … <span className="text-xs text-slate-400 block">manager</span></div>
                    <div className="bg-slate-100 p-2 rounded">mlt / … <span className="text-xs text-slate-400 block">scientist</span></div>
                    <div className="bg-slate-100 p-2 rounded">medic / … <span className="text-xs text-slate-400 block">medic</span></div>
                    <div className="bg-slate-100 p-2 rounded">pathologist / … <span className="text-xs text-slate-400 block">medic · Pathology</span></div>
                    <div className="bg-slate-100 p-2 rounded">testuser / … <span className="text-xs text-slate-400 block">clerk · Reception</span></div>
                </div>
                <p className="text-xs text-slate-500 mt-2">Passwords bcrypt-hashed in the users table. Change all defaults before any production exposure.</p>
            </Card>
        </section>
    );
}

// ==========================================
// 13. CHANGELOG & HISTORY
// ==========================================
function ChangelogSection() {
    return (
        <section className="space-y-8">
            <Header title="Changelog & Feature History" subtitle="Timeline of system capabilities and major releases." />

            <div className="relative border-l-2 border-slate-200 ml-4 space-y-12">

                <ReleaseNode
                    version="v2.0.1"
                    date="2026-06-11"
                    title="Cohesion, QA Hardening & Runtime Fixes"
                    features={[
                        "Migration integrity: fixed apply-new-tables.js path bug that created the 24 clinical tables in a stray parent-directory DB; all tables now verified in sqlite_v2.db.",
                        "Audit trail restored: logAudit now always writes through Drizzle — previously crashed (db.insert is not a function) and silently dropped all audit entries.",
                        "Reference-range contract unified: clinical engine and report flagging now read the canonical { min, max, panicLow, panicHigh } shape — critical detection and H/L/C flags actually fire.",
                        "Reflex rules act: triggered rules now append the add-on test to the order's testIds (previously recorded but never added).",
                        "Epidemiology auto-detection: results on tests linked to active notifiable conditions now auto-create Pending notifications.",
                        "E-signatures recorded server-side on TECHNICAL_VALIDATE / CLINICAL_VERIFY with IP + user agent; rendered on reports.",
                        "Results route consolidation: removed full-DB readDb/writeDb rewrite per result save; single Drizzle update sets status, completedAt, queueId.",
                        "Dashboard truth: stats + drill-downs use correct status casing, the timestamp column, and criticalValueNotifications as the critical source.",
                        "Orders API enrichment: GET /api/orders returns patientName/Mrn/Dob/Gender; queues page shows names, not UUIDs.",
                        "Full QA pass: 38 API tests, browser console sweep of ~25 pages (zero errors), RBAC verification, end-to-end workflow trace."
                    ]}
                />

                <ReleaseNode
                    version="v2.0.0"
                    date="2026-06-11"
                    title="Clinical Engine & Enterprise Gap Closure (27 features)"
                    features={[
                        "Clinical decision engine: delta checks, critical value detection + acknowledgment workflow, reflex testing, demographic reference ranges, calculated tests (LDL Friedewald, anion gap, A/G ratio, eGFR CKD-EPI).",
                        "Pre-analytical: specimen receiving (accept/reject with condition, temperature, volume), phlebotomy scheduling.",
                        "Post-analytical: electronic result signatures, branded report redesign with flag colouring, cumulative (flowsheet) reports.",
                        "Compliance: TAT thresholds + breach monitoring, user competency tracking, specimen retention + disposal, LOINC catalogue with test linking, requester registry, distribution rules.",
                        "Surveillance: notifiable conditions registry + epidemiology notification workflow (Pending→Reviewed→Submitted→Closed).",
                        "Analytics: KPI dashboard (volume, TAT compliance, rejection rate, top tests).",
                        "Platform: 24 new tables, ~40 new API endpoints, 16 new pages, sidebar restructure; unified auth helper (src/lib/auth.ts) and dual-cookie login fix."
                    ]}
                />

                <ReleaseNode
                    version="v1.6.0"
                    date="2025-12-22"
                    title="Surveillance & Deployment Hardening"
                    features={[
                        "Server-Side Accessioning: Atomic, sequential ID generation (YYYY-MM-DD-XXXX) to eliminate race conditions.",
                        "Surveillance Module: Epidemiology CSV Export tool for mandatory reporting (HIV, Malaria, TB).",
                        "Deployment Ready: Dockerfile and docker-compose.yml added for containerized production capability.",
                        "API Hardening: Transactional integrity added to key Order creation endpoints."
                    ]}
                />

                <ReleaseNode
                    version="v1.5.1"
                    date="2025-12-18"
                    title="Workflow Integrity & Maintenance Patch"
                    features={[
                        "Queue Integration: 'Submit for Tech Validation' now correctly routes to technical queue.",
                        "Database Sync: Fixed synchronization between Results (SQLite) and Worklist (JSON) engines.",
                        "Audit Archiving: Added missing UI for log retention and purging.",
                        "Stability: Improved error handling in result verification workflow."
                    ]}
                />

                <ReleaseNode
                    version="v1.5.0"
                    date="2025-12-18"
                    title="Department Governance & System-Wide Enforcement"
                    features={[
                        "Department Toggle: Enable/disable departments with admin password verification.",
                        "System-Wide Enforcement: Disabled departments hide from accessioning, messaging, and inventory.",
                        "Protected Admin Views: Admins still see all departments/tests for management purposes.",
                        "API Query Parameters: ?includeDisabled=true and ?includeDisabledDepts=true for admin access.",
                        "Audit Logging: All department status changes logged with user and timestamp.",
                        "Visual Indicators: Disabled departments show faded cards with 'DISABLED' badge."
                    ]}
                />

                <ReleaseNode
                    version="v1.4.0"
                    date="2025-12-18"
                    title="System-Wide Theming & Appearance"
                    features={[
                        "Dynamic Theming: 5 color schemes (Clinical Blue, Bio-Emerald, Hematology Crimson, Deep Indigo, High Contrast).",
                        "Dark Mode: Full dark interface for microscopy/low-light environments.",
                        "Instant Preview: Theme changes apply immediately without page refresh.",
                        "Role-Based Access: Theme configuration restricted to Admins and Managers.",
                        "Persistent Sidebar: Left menu maintains dark appearance in both light and dark modes.",
                        "CSS Variable Architecture: Tailwind configured with dynamic CSS variables for runtime theming."
                    ]}
                />

                <ReleaseNode
                    version="v1.3.0"
                    date="2025-12-18"
                    title="Enterprise Structure & Partitioning"
                    features={[
                        "Laboratory Departments: API & UI to support independent units (Micro, Histo, Genetics).",
                        "Resource Partitioning: Assign specific Users, Inventory, and Tests to specific Departments.",
                        "Internal Broadcasting: Send messages to 'All Staff' or specific Departments.",
                        "Email Integration: Real SMTP Configuration (Gmail/Outlook) via Admin Settings.",
                        "Inventory Management: Full CRUD for reagents/consumables with 'Shared' or 'Lab-Specific' allocation.",
                        "Comprehensive Lab Seed: Auto-provisioning of 13+ standard clinical laboratory types."
                    ]}
                />

                <ReleaseNode
                    version="v1.2.0"
                    date="2025-12-18"
                    title="Communication & Data Tools"
                    features={[
                        "Internal Messaging System: User-to-user inbox with 'Urgent' flagging.",
                        "Email Reporting: Manual queueing and batch delivery of results via SMTP hook.",
                        "Demo Data Generator: 'Seed Data' admin tool to populate 5 random patients.",
                        "Developer Bible: Massive expansion of internal documentation.",
                        "Security: AES-256-GCM Backup Encryption."
                    ]}
                />

                <ReleaseNode
                    version="v1.1.0"
                    date="2025-12-18"
                    title="Advanced Clinical LIS Features"
                    features={[
                        "Patient Trends: Longitudinal graphical analysis of test history.",
                        "Cumulative Reports: Table view of all historical results for a patient.",
                        "Middleware API: '/api/middleware/ingest' for automated instrument results.",
                        "Work Queues: Role-based lists (Technical vs Clinical Validation).",
                        "Audit Trail: Comprehensive logging of all CREATE/UPDATE actions."
                    ]}
                />

                <ReleaseNode
                    version="v1.0.0"
                    date="2025-12-18"
                    title="MVP Core Functionality"
                    features={[
                        "Accessioning: Order entry and specimen tracking.",
                        "Result Entry: Manual verification grid with reference range flagging.",
                        "Patient Management: CRUD operations with fuzzy search.",
                        "RBAC: Admin, Manager, Scientist, Medic roles.",
                        "Dashboard: Real-time KPIs (Turnaround Time, Pending Orders)."
                    ]}
                />
            </div>
        </section>
    );
}

// ==========================================
// UTILITIES
// ==========================================

function Header({ title, subtitle }: any) {
    return (
        <div className="border-b border-slate-200 pb-4 mb-6">
            <h2 className="text-3xl font-bold text-slate-900">{title}</h2>
            <p className="text-lg text-slate-500 mt-2">{subtitle}</p>
        </div>
    );
}

function SchemaItem({ name, fields, desc }: any) {
    return (
        <Card title={name} className="overflow-hidden">
            <div className="px-6 py-2 bg-slate-50 border-b text-sm text-slate-600 italic">
                {desc}
            </div>
            <table className="w-full text-sm text-left">
                <thead className="bg-white border-b">
                    <tr>
                        <th className="p-3 pl-6 w-48">Property</th>
                        <th className="p-3 w-32">Type</th>
                        <th className="p-3">Description</th>
                    </tr>
                </thead>
                <tbody className="divide-y">
                    {fields.map((f: any, i: number) => (
                        <tr key={i} className="hover:bg-slate-50/50">
                            <td className="p-3 pl-6 font-mono text-primary-700 font-semibold">{f.name}</td>
                            <td className="p-3 font-mono text-purple-600 text-xs bg-purple-50 rounded w-fit px-2 py-1 inline-block my-1">{f.type}</td>
                            <td className="p-3 text-slate-600">{f.desc}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </Card>
    );
}

function ApiBlock({ method, route, desc, queries, body, response }: any) {
    return (
        <div className="border border-slate-200 rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow">
            <div className="bg-slate-50 p-4 border-b flex justify-between items-center cursor-pointer">
                <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded text-xs font-bold text-white w-16 text-center shadow-sm
                        ${method === 'GET' ? 'bg-blue-600' : ''}
                        ${method === 'POST' ? 'bg-green-600' : ''}
                        ${method === 'PUT' ? 'bg-amber-600' : ''}
                        ${method === 'DELETE' ? 'bg-red-600' : ''}
                    `}>{method}</span>
                    <code className="text-sm font-bold text-slate-800 font-mono">{route}</code>
                </div>
                <span className="text-xs text-slate-500 uppercase tracking-wide font-semibold">{desc}</span>
            </div>

            <div className="p-6 space-y-6 bg-white">
                {queries && (
                    <div>
                        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Query Parameters</h4>
                        <div className="grid grid-cols-1 gap-2">
                            {queries.map((q: any, i: number) => (
                                <div key={i} className="flex gap-4 text-sm border-b border-dashed border-slate-100 pb-2">
                                    <code className="text-primary-700 font-bold min-w-[100px]">{q.param}</code>
                                    <span className="text-slate-600">{q.desc}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {body && (
                    <div>
                        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Request Body</h4>
                        <pre className="bg-slate-900 text-slate-50 p-4 rounded-lg text-xs font-mono overflow-x-auto shadow-inner border border-slate-700">
                            {body}
                        </pre>
                    </div>
                )}

                <div>
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Response Example</h4>
                    <pre className="bg-slate-50 text-slate-600 p-4 rounded-lg text-xs font-mono overflow-x-auto border border-slate-200">
                        {response}
                    </pre>
                </div>
            </div>
        </div>
    );
}

function ArrowDown() {
    return <div className="text-slate-300">↓</div>;
}

function AlertBox({ type, title, children }: any) {
    const styles = {
        warning: 'bg-amber-50 border-amber-200 text-amber-800',
        info: 'bg-blue-50 border-blue-200 text-blue-800'
    } as any;

    return (
        <div className={`p-4 rounded border ${styles[type]} flex gap-3`}>
            {type === 'warning' && <AlertTriangle className="w-5 h-5 shrink-0" />}
            <div>
                <strong className="block text-sm font-bold mb-1">{title}</strong>
                <div className="text-sm opacity-90">{children}</div>
            </div>
        </div>
    );
}

function ReleaseNode({ version, date, title, features }: any) {
    return (
        <div className="relative pl-8">
            {/* Timeline Dot */}
            <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-primary-600 border-4 border-white shadow-sm"></div>

            <div className="mb-2 flex items-center gap-3">
                <span className="font-mono text-sm font-bold bg-slate-900 text-white px-2 py-0.5 rounded">{version}</span>
                <span className="text-sm text-slate-500 font-medium">{date}</span>
            </div>

            <h3 className="text-lg font-bold text-slate-900 mb-3">{title}</h3>

            <Card className="border-t-4 border-t-primary-500">
                <ul className="space-y-3">
                    {features.map((f: string, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                            <CheckCircleIcon className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                            <span>{f}</span>
                        </li>
                    ))}
                </ul>
            </Card>
        </div>
    );
}

function CheckCircleIcon(props: any) {
    return (
        <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
    );
}
