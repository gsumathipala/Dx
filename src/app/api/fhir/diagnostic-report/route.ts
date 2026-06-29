import { NextResponse } from 'next/server';
import { readDb } from '@/lib/db';
import { db as drizzleDb } from '@/db';
import { testDefinitions } from '@/db/schema';

/**
 * FHIR R4 DiagnosticReport API Facade
 * 
 * Maps internal LIS data models to HL7 FHIR R4 JSON resources.
 * Returns a "searchset" Bundle containing:
 * 1. DiagnosticReport (Root)
 * 2. Patient (Subject)
 * 3. Observation (Results)
 * 
 * Capability: Read-only access to finalized reports suitable for EHR ingestion.
 */

// Helper to standardise status
const mapStatus = (lisStatus: string) => {
    switch (lisStatus) {
        case 'Completed': return 'final';
        case 'Pending Validation':
        case 'Technically Validated': return 'preliminary';
        case 'Cancelled': return 'cancelled';
        default: return 'registered';
    }
};

export async function GET(request: Request) {
    // Auth: require valid session cookie (same as all other routes)
    const { cookies } = await import('next/headers');
    const cookieStore = await cookies();
    const token = cookieStore.get('auth_token')?.value;
    if (!token) {
        return NextResponse.json(
            { resourceType: 'OperationOutcome', issue: [{ severity: 'error', code: 'security', diagnostics: 'Authentication required' }] },
            { status: 401 }
        );
    }

    try {
        const { searchParams } = new URL(request.url);
        const orderId = searchParams.get('orderId');
        const accession = searchParams.get('accession');

        if (!orderId && !accession) {
            return NextResponse.json({
                resourceType: "OperationOutcome",
                issue: [{ severity: "error", code: "required", diagnostics: "Missing orderId or accession parameter" }]
            }, { status: 400 });
        }

        const db = await readDb();

        // Load test definitions from Drizzle (has loincCode; legacy readDb does not)
        const allTestDefs = await drizzleDb.select().from(testDefinitions);

        // 2. Find Order
        let order;
        if (orderId) {
            order = db.orders.find((o: any) => o.id === orderId);
        } else {
            order = db.orders.find((o: any) => o.accessionNumber === accession);
        }

        if (!order) {
            return NextResponse.json({ resourceType: "OperationOutcome", issue: [{ severity: "error", code: "not-found" }] }, { status: 404 });
        }

        // 3. Find Related Data
        const results = db.results.find((r: any) => r.orderId === order.id); // Get latest result record
        const patientSpec = order.patientId ? db.patients?.find((p: any) => p.id === order.patientId) : null;

        // 4. Construct FHIR Resources

        // Resource: Patient
        const patientResourceId = patientSpec ? `pat-${patientSpec.id}` : `pat-unknown`;
        const fhirPatient = {
            resourceType: "Patient",
            id: patientResourceId,
            identifier: [
                { system: "http://hospital.org/mrn", value: patientSpec?.mrn || order.patientId }
            ],
            name: [
                { use: "official", family: patientSpec?.lastName, given: [patientSpec?.firstName] }
            ],
            gender: patientSpec?.gender?.toLowerCase() || "unknown",
            birthDate: patientSpec?.dob
        };

        // Resources: Observations (Test Results)
        const observations = [];
        const resultValues = results?.values?.results || {};

        for (const testId of (order.testIds || [])) {
            const testDef = allTestDefs.find(t => t.id === testId);
            const value = resultValues[testId];

            if (value) {
                const isNumeric = !isNaN(parseFloat(value));
                const loincCode = testDef?.loincCode || null;

                observations.push({
                    resourceType: "Observation",
                    id: `obs-${order.id}-${testId}`,
                    status: mapStatus(order.status),
                    code: {
                        coding: loincCode ? [
                            { system: "http://loinc.org", code: loincCode, display: testDef?.name }
                        ] : [],
                        text: testDef?.name
                    },
                    subject: {
                        reference: `Patient/${patientResourceId}`,
                        display: patientSpec ? `${patientSpec.firstName} ${patientSpec.lastName}` : undefined
                    },
                    effectiveDateTime: results?.timestamp || order.timestamp,
                    performer: [{ display: results?.enteredBy || "Lab" }],
                    valueQuantity: isNumeric ? {
                        value: parseFloat(value),
                        unit: testDef?.units,
                        system: "http://unitsofmeasure.org",
                        code: testDef?.units
                    } : undefined,
                    valueString: !isNumeric ? value : undefined,
                    referenceRange: testDef?.referenceRange ? [{
                        text: testDef.referenceRange
                    }] : undefined
                });
            }
        }

        // Resource: DiagnosticReport
        const fhirReport = {
            resourceType: "DiagnosticReport",
            id: `rpt-${order.id}`,
            identifier: [
                { system: "http://lab.org/accession", value: order.accessionNumber }
            ],
            status: mapStatus(order.status),
            category: [
                { coding: [{ system: "http://terminology.hl7.org/CodeSystem/v2-0074", code: "LAB", display: "Laboratory" }] }
            ],
            code: {
                text: "Laboratory Report"
                // In real world, this would be the LOINC for the Panel (e.g. 24331-1 for Lipid Panel)
            },
            subject: { reference: `Patient/${patientResourceId}` },
            effectiveDateTime: order.timestamp,
            issued: results?.timestamp || new Date().toISOString(),
            performer: [{ display: "Dx Clinical Lab" }],
            result: observations.map(obs => ({ reference: `Observation/${obs.id}` }))
        };

        // 5. Construct Bundle
        const bundle = {
            resourceType: "Bundle",
            type: "searchset",
            total: 3, // approximate
            timestamp: new Date().toISOString(),
            entry: [
                { fullUrl: `urn:uuid:${fhirReport.id}`, resource: fhirReport },
                { fullUrl: `urn:uuid:${fhirPatient.id}`, resource: fhirPatient },
                ...observations.map(obs => ({ fullUrl: `urn:uuid:${obs.id}`, resource: obs }))
            ]
        };

        return NextResponse.json(bundle);

    } catch (error) {
        console.error("FHIR API Error:", error);
        return NextResponse.json({
            resourceType: "OperationOutcome",
            issue: [{ severity: "fatal", code: "exception", diagnostics: "Internal Server Error" }]
        }, { status: 500 });
    }
}
