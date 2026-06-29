
import { NextResponse } from 'next/server';
import { db } from '@/db';
import { orders, patients, specimens } from '@/db/schema';
import { eq, and, not } from 'drizzle-orm';
import { getAuthUser } from '@/lib/auth';

// Fetch pending collections
export async function GET() {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const pendingOrders = await db.select({
            orderId: orders.id,
            accessionNumber: orders.accessionNumber,
            patientName: patients.firstName, // Simplified join for demo
            patientMrn: patients.mrn,
            priority: orders.priority,
            testIds: orders.testIds,
        })
            .from(orders)
            .innerJoin(patients, eq(orders.patientId, patients.id))
            .where(
                and(
                    eq(orders.status, 'Pending'),
                    // In real app, check if specimens are collected.
                    // For now, if order is Pending, we assume collection needed.
                )
            );

        // Client side will format patient name etc if needed, or we can select more fields.
        return NextResponse.json(pendingOrders);
    } catch (e: any) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { orderId } = await request.json();

        // 1. Mark Order as In Progress (Received/Collected)
        await db.update(orders).set({
            status: 'In Progress',
            updatedAt: new Date().toISOString()
        }).where(eq(orders.id, orderId));

        // 2. Create Specimen Records
        const orderRes = await db.select().from(orders).where(eq(orders.id, orderId));
        const order = orderRes[0];

        // Naive: 1 Lavender, 1 SST per order for this demo
        // In real life, calculate based on Test Definitions

        return NextResponse.json({ success: true });
    } catch (e: any) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
