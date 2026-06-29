import { NextResponse } from 'next/server';
import { db } from '@/db';
import { deltaCheckFlags, orders, patients, testDefinitions } from '@/db/schema';
import { eq, and, isNull } from 'drizzle-orm';
import { cookies } from 'next/headers';

async function getCurrentUser() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return null;
    try {
        return JSON.parse(session.value);
    } catch {
        return null;
    }
}

// GET /api/delta-checks/flags — returns all unacknowledged flags with patient/test info
// Query params: ?orderId=<id> to filter by order
export async function GET(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const { searchParams } = new URL(request.url);
        const orderId = searchParams.get('orderId');

        // Fetch unacknowledged flags
        let flags;
        if (orderId) {
            flags = await db.select().from(deltaCheckFlags).where(
                and(eq(deltaCheckFlags.orderId, orderId), isNull(deltaCheckFlags.acknowledgedBy))
            );
        } else {
            flags = await db.select().from(deltaCheckFlags).where(isNull(deltaCheckFlags.acknowledgedBy));
        }

        // Enrich with order/patient/test info
        const enriched = await Promise.all(flags.map(async (flag) => {
            let patientName = '';
            let mrn = '';
            let accessionNumber = '';
            let testCode = '';
            let testName = '';

            try {
                const orderRows = await db.select().from(orders).where(eq(orders.id, flag.orderId)).limit(1);
                if (orderRows.length > 0) {
                    accessionNumber = orderRows[0].accessionNumber;
                    const patientRows = await db.select().from(patients).where(eq(patients.id, orderRows[0].patientId)).limit(1);
                    if (patientRows.length > 0) {
                        patientName = `${patientRows[0].firstName} ${patientRows[0].lastName}`;
                        mrn = patientRows[0].mrn;
                    }
                }
            } catch { /* non-fatal */ }

            try {
                const testRows = await db.select().from(testDefinitions).where(eq(testDefinitions.id, flag.testId)).limit(1);
                if (testRows.length > 0) {
                    testCode = testRows[0].code;
                    testName = testRows[0].name;
                }
            } catch { /* non-fatal */ }

            return {
                ...flag,
                patientName,
                mrn,
                accessionNumber,
                testCode,
                testName,
            };
        }));

        return NextResponse.json(enriched);
    } catch (error) {
        console.error('GET delta-check flags error:', error);
        return NextResponse.json({ error: 'Failed to fetch delta check flags' }, { status: 500 });
    }
}

// PUT /api/delta-checks/flags — acknowledge a flag
// Body: { flagId, acknowledgedBy }
export async function PUT(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const body = await request.json();
        const { flagId, acknowledgedBy } = body;

        if (!flagId) {
            return NextResponse.json({ error: 'Missing flagId' }, { status: 400 });
        }

        const existing = await db.select().from(deltaCheckFlags).where(eq(deltaCheckFlags.id, flagId)).limit(1);
        if (existing.length === 0) {
            return NextResponse.json({ error: 'Flag not found' }, { status: 404 });
        }

        await db.update(deltaCheckFlags).set({
            acknowledgedBy: acknowledgedBy || currentUser.username,
            acknowledgedAt: new Date().toISOString(),
        }).where(eq(deltaCheckFlags.id, flagId));

        const updated = await db.select().from(deltaCheckFlags).where(eq(deltaCheckFlags.id, flagId)).limit(1);
        return NextResponse.json(updated[0]);
    } catch (error) {
        console.error('PUT delta-check flag error:', error);
        return NextResponse.json({ error: 'Failed to acknowledge flag' }, { status: 500 });
    }
}
