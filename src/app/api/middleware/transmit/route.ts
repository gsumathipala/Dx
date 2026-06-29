import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager', 'scientist'].includes(currentUser.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    try {
        const body = await request.json();
        const { instrumentId, transmissions } = body;
        // transmissions: [{ accessionNumber, testId, value, timestamp }]

        const db = await readDb();
        const resultsLog: any[] = [];
        const testDefs = db.testDefinitions || [];

        for (const tx of transmissions) {
            // 1. Find Order
            const order = db.orders.find((o: any) => o.accessionNumber === tx.accessionNumber);
            if (!order) {
                resultsLog.push({ ...tx, status: 'Error', message: 'Order not found' });
                continue;
            }

            // 2. Find Existing Result Entry or Create New
            const resultIndex = db.results.findIndex((r: any) => r.orderId === order.id);
            const resultEntry = resultIndex >= 0 ? db.results[resultIndex] : {
                id: Date.now().toString() + Math.random(),
                orderId: order.id,
                values: { results: {} },
                timestamp: new Date().toISOString(),
                performedBy: `Instrument: ${instrumentId}`,
                status: 'Preliminary'
            };

            // 3. Update Value
            if (!resultEntry.values) resultEntry.values = { results: {} };
            if (!resultEntry.values.results) resultEntry.values.results = {};

            resultEntry.values.results[tx.testId] = tx.value;

            // 4. Run Auto-Validation (Mini-Engine)
            // Check if ALL results in this order (now including new one) are valid
            let allNormal = true;
            for (const [tId, val] of Object.entries(resultEntry.values.results)) {
                const testDef = testDefs.find((t: any) => t.id === tId);
                if (testDef && testDef.referenceRange) {
                    const [min, max] = testDef.referenceRange.split('-').map((s: string) => parseFloat(s.trim()));
                    const numVal = parseFloat(val as string);
                    if (isNaN(min) || isNaN(max) || isNaN(numVal) || numVal < min || numVal > max) {
                        allNormal = false;
                        break;
                    }
                }
            }

            if (allNormal) {
                resultEntry.status = 'Completed';
                resultEntry.performedBy = `Auto-Val (${instrumentId})`;
                if (!resultEntry.values.internalComments) resultEntry.values.internalComments = '';
                resultEntry.values.internalComments += `\n[Middleware] Rx from ${instrumentId}: ${tx.value}. Auto-Validated.`;
            } else {
                resultEntry.status = 'Preliminary'; // Stay prelim if abnormal
                if (!resultEntry.values.internalComments) resultEntry.values.internalComments = '';
                resultEntry.values.internalComments += `\n[Middleware] Rx from ${instrumentId}: ${tx.value}. Held for review.`;
            }

            // 5. Save Back
            if (resultIndex >= 0) {
                db.results[resultIndex] = resultEntry;
            } else {
                db.results.push(resultEntry);
                // Also update order status
                if (order.status === 'Pending') {
                    // If it's the first result, we might keep order as In Progress
                    const orderIndex = db.orders.findIndex((o: any) => o.id === order.id);
                    db.orders[orderIndex].status = 'In Progress';
                }
            }

            // Allow order status to complete if result is complete
            if (resultEntry.status === 'Completed') {
                const orderIndex = db.orders.findIndex((o: any) => o.id === order.id);
                db.orders[orderIndex].status = 'Completed';
            }

            resultsLog.push({ ...tx, status: 'Success' });
        }

        await writeDb(db);
        return NextResponse.json({ message: 'Batch Processed', log: resultsLog });

    } catch (error) {
        console.error(error);
        return NextResponse.json({ error: 'Middleware Error' }, { status: 500 });
    }
}
