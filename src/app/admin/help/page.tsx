"use client";

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';

const ADMIN_SECTIONS = [
    {
        title: "1. System Architecture & Data Storage",
        content: (
            <div className="space-y-3 text-sm text-slate-700">
                <p>Dx LIS runs on a <strong>Serverless / Node.js</strong> architecture (Next.js Framework).</p>
                <ul className="list-disc pl-5 space-y-1">
                    <li><strong>Runtime:</strong> Node.js v18+</li>
                    <li><strong>Database Engine:</strong> JSON-based Flat File capability (Prototype) / SQLite Compatible.</li>
                    <li><strong>Data Path:</strong> <code>/data/db.json</code> (Primary Persistence).</li>
                    <li><strong>File Storage:</strong> Local filesystem for reports/logs.</li>
                </ul>
                <div className="bg-blue-50 p-3 border-l-4 border-blue-500 mt-2">
                    <strong>Backup Strategy:</strong> The system supports hot-backups. Use the <em>System Maintenance</em> page to generate atomic snapshots of the `db.json` state.
                </div>
            </div>
        )
    },
    {
        title: "2. API Integration Manual (FHIR & Internal)",
        content: (
            <div className="space-y-4">
                <p className="text-sm">The system exposes a RESTful API Facade for interoperability.</p>

                {/* FHIR Section */}
                <div className="border rounded p-4 bg-slate-50">
                    <h4 className="font-bold text-slate-900 border-b pb-2 mb-2">A. HL7 FHIR R4 Interface (EHR Integration)</h4>
                    <p className="text-xs text-slate-500 mb-2">Standardized endpoint for pulling results into Epic/Cerner/EMR.</p>

                    <div className="space-y-2">
                        <div className="flex gap-2 items-center">
                            <span className="px-2 py-1 bg-green-100 text-green-800 text-xs font-bold rounded">GET</span>
                            <code className="text-xs bg-slate-200 px-2 py-1 rounded w-full">/api/fhir/diagnostic-report?accession=ACC-20241218-001</code>
                        </div>
                        <div className="flex gap-2 items-center">
                            <span className="px-2 py-1 bg-green-100 text-green-800 text-xs font-bold rounded">GET</span>
                            <code className="text-xs bg-slate-200 px-2 py-1 rounded w-full">/api/fhir/diagnostic-report?orderId=1700000000</code>
                        </div>
                    </div>

                    <div className="mt-3">
                        <p className="text-xs font-bold mb-1">Response Schema (Bundle):</p>
                        <pre className="bg-slate-900 text-green-400 p-3 rounded text-[10px] overflow-x-auto">
                            {`{
  "resourceType": "Bundle",
  "type": "searchset",
  "entry": [
    {
      "resource": {
        "resourceType": "DiagnosticReport",
        "status": "final",
        "code": { "coding": [{ "system": "http://loinc.org", "code": "24331-1" }] },
        "result": [ { "reference": "Observation/obs-1" } ]
      }
    },
    { "resource": { "resourceType": "Patient", ... } },
    { "resource": { "resourceType": "Observation", "valueQuantity": { "value": 5.5, "unit": "mmol/L" } } }
  ]
}`}
                        </pre>
                    </div>
                </div>

                {/* Internal API Section */}
                <div className="border rounded p-4 bg-slate-50">
                    <h4 className="font-bold text-slate-900 border-b pb-2 mb-2">B. Administration APIs</h4>
                    <ul className="space-y-2 text-xs">
                        <li>
                            <strong>User Management:</strong>
                            <br />
                            <code>POST /api/admin/users</code> - Create User
                            <br />
                            <code>DELETE /api/admin/users?id=X</code> - Remove User (Requires JSON body `password`)
                        </li>
                        <li>
                            <strong>System Maintenance:</strong>
                            <br />
                            <code>POST /api/admin/maintenance</code> - Trigger VACUUM or Integrity Check.
                        </li>
                    </ul>
                </div>
            </div>
        )
    },
    {
        title: "3. Security & Compliance Internals",
        content: (
            <div className="space-y-3 text-sm text-slate-700">
                <h4 className="font-bold font-mono">Authentication</h4>
                <p>Session management uses <code>httpOnly</code> cookies (`auth_session`). Passwords are stored in the database (Prototype Mode: Cleartext / Production: Should be BCrypt hashed).</p>

                <h4 className="font-bold font-mono mt-2">Audit Immutability</h4>
                <p>The system utilizes an append-only logic for the `auditLog` array in `db.json`. The implementation prevents `pop()` or index-based modification of existing logs via the API. Archiving performs a copy-then-purge operation wrapped in a transaction.</p>

                <h4 className="font-bold font-mono mt-2">Queue Logic</h4>
                <p>Authorization queues allow managers to segregate workload. The logic enforces that a user cannot verify their own results (Self-Verification Block), compliant with CLIA regulations.</p>
            </div>
        )
    }
];

export default function AdminHelpPage() {
    return (
        <div className="max-w-4xl space-y-6 pb-12">
            <h1 className="text-3xl font-bold text-slate-900">System Administrator Manual</h1>
            <div className="bg-amber-100 border-l-4 border-amber-500 p-4 text-amber-800">
                <strong>Confidential:</strong> This document contains internal system architecture and API details. Do not distribute to general staff.
            </div>

            <div className="grid grid-cols-1 gap-6">
                {ADMIN_SECTIONS.map((section, idx) => (
                    <Card key={idx} title={section.title}>
                        {section.content}
                    </Card>
                ))}
            </div>
        </div>
    );
}
