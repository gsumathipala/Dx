import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit, evaluateResult } from '@/lib/db';

/**
 * MIDDLEWARE INGESTION API (Solves Issue #4 & #17)
 * 
 * Simulates an endpoint receiving result data from an Interface Engine (ie: Mirth Connect).
 * Accepts JSON payloads mapped from HL7 ORU messages.
 */
export async function POST(request: Request) {
    try {
        // Authenticate (Basic API Key simulation)
        const authHeader = request.headers.get('authorization');
        const secret = process.env.MIDDLEWARE_SECRET_KEY;
        if (!secret) {
            console.warn('[MIDDLEWARE] MIDDLEWARE_SECRET_KEY env var is not set — ingest endpoint is unprotected');
        } else if (authHeader !== `Bearer ${secret}`) {
            return NextResponse.json({ error: 'Unauthorized Interface' }, { status: 401 });
        }

        const body = await request.json();
        const { instrumentId, sampleId, timestamp, results } = body;
        // results: [{ testCode: 'HGB', value: '14.5', units: 'g/dL', flags: '' }]

        if (!sampleId || !results || !Array.isArray(results)) {
            return NextResponse.json({ error: 'Invalid payload format' }, { status: 400 });
        }

        const db = await readDb();

        // 1. Find the Order associated with this Sample ID
        // In our simplified schema, sampleId often links directly to orderId or a specimen within it.
        // Let's assume sampleId matches an Order ID for now, or we search orders.
        const orderIndex = db.orders.findIndex((o: any) => o.id === sampleId || (o.samples && o.samples.some((s: any) => s.id === sampleId)));

        if (orderIndex === -1) {
            return NextResponse.json({ error: 'Order/Sample not found' }, { status: 404 });
        }

        const order = db.orders[orderIndex];
        const updates: any[] = [];

        // 2. Process Results
        for (const res of results) {
            // Find test definition to check ranges
            const testDef = db.testDefinitions.find((t: any) => t.code === res.testCode || t.id === res.testCode);

            // Auto-Validation / Delta Logic (Issue #22)
            let evaluation: any = { status: 'normal', flag: '' };
            if (testDef && testDef.referenceRange) {
                evaluation = evaluateResult(res.value, testDef.referenceRange);
            }

            // Create Result Record
            const newResult = {
                id: `res-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
                orderId: order.id,
                testId: testDef ? testDef.id : res.testCode,
                testName: testDef ? testDef.name : res.testCode,
                value: res.value,
                unit: res.units || testDef?.units || '',
                status: 'Preliminary', // Middleware results usually come in as Prelim
                flags: evaluation.flag || res.flags,
                referenceRange: testDef ? (testDef.referenceRange.text || `${testDef.referenceRange.min}-${testDef.referenceRange.max}`) : '',
                instrument: instrumentId,
                performedAt: timestamp || new Date().toISOString(),
                enteredBy: 'MIDDLEWARE'
            };

            db.results.push(newResult);
            updates.push(newResult);
        }

        // 3. Update Order Status
        if (order.status === 'Received' || order.status === 'Pending') {
            db.orders[orderIndex].status = 'In Progress';
        }

        // 4. Audit
        await logAudit(db, 'Order', order.id, 'UPDATE', null, { resultsAdded: updates.length }, 'system-middleware');

        await writeDb(db);

        return NextResponse.json({
            success: true,
            message: `Processed ${updates.length} results for Sample ${sampleId}`,
            results: updates
        });

    } catch (error) {
        console.error('Middleware error:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
