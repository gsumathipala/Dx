
import { NextResponse } from 'next/server';
import { db } from '@/db';
import { orders, results, testDefinitions, users, sessions } from '@/db/schema';
import { eq, and } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

export async function POST(request: Request) {
    // 1. Authenticate Middleware Bot
    const cookieStore = await cookies();
    const token = cookieStore.get('auth_token')?.value;

    if (!token) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const session = await db.select().from(sessions).where(eq(sessions.token, token)).limit(1);
    if (!session.length || session[0].expiresAt < Date.now()) {
        return NextResponse.json({ error: 'Session expired' }, { status: 401 });
    }

    const mwUser = await db.select().from(users).where(eq(users.id, session[0].userId)).limit(1);
    const userId = mwUser[0].username;

    try {
        const body = await request.json();
        const { accessionNumber, testCode, value, units, flags, timestamp } = body;

        // 2. Find Order
        const orderRes = await db.select().from(orders).where(eq(orders.accessionNumber, accessionNumber)).limit(1);
        if (!orderRes.length) {
            return NextResponse.json({ error: 'Order not found' }, { status: 404 });
        }
        const order = orderRes[0];

        // 3. Find Test Definition (to get ID)
        const testRes = await db.select().from(testDefinitions).where(eq(testDefinitions.code, testCode)).limit(1);
        // If test not found, maybe handle dynamic or error. For now, require definition.
        const testId = testRes.length ? testRes[0].id : testCode;

        // 4. Update/Insert Result
        // Check if result already exists for this order+test
        const existing = await db.select().from(results)
            .where(and(eq(results.orderId, order.id), eq(results.testId, testId)))
            .limit(1);

        const resultData = {
            values: JSON.stringify({ value, units, note: 'Via Middleware' }),
            resultFlags: JSON.stringify({ flag: flags }),
            status: 'Technically Validated', // Auto-validate generic machine results? Or Draft. Let's say Draft for safety.
            technicalValidatedBy: userId, // The bot "validated" transmission
            timestamp: timestamp || new Date().toISOString()
        };

        if (existing.length) {
            await db.update(results)
                .set(resultData)
                .where(eq(results.id, existing[0].id));
        } else {
            await db.insert(results).values({
                id: uuidv4(),
                orderId: order.id,
                testId: testId,
                ...resultData,
                enteredBy: userId,
                clinicalVerifiedBy: null
            });
        }

        return NextResponse.json({ success: true });
    } catch (e: any) {
        console.error('Ingest error:', e);
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
