import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { cookies } from 'next/headers';

async function getSessionUser() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return null;
    try { return JSON.parse(session.value); } catch { return null; }
}

export async function GET(request: Request) {
    const currentUser = await getSessionUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager', 'clerk'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    const db = await readDb();
    const orders = db.orders || [];
    const testDefs = db.testDefinitions || [];

    // Filter for billable orders (Completed)
    const billableOrders = orders.filter((o: any) => o.status === 'Completed').map((o: any) => {
        // Calculate Total
        let total = 0;
        const lineItems = (o.testIds || []).map((tId: string) => {
            const test = testDefs.find((t: any) => t.id === tId);
            // Lookup billing item by test code or ID (assuming test.code matches billingItem.code)
            const billingItem = db.billingItems?.find((b: any) => b.code === test?.code || b.code === tId);
            const price = billingItem?.price ? Number(billingItem.price) : 0;
            total += price;
            return { name: test?.name || tId, price };
        });

        return {
            ...o,
            lineItems,
            total,
            paymentStatus: db.orderPayments?.[o.id]?.status || 'Unpaid',
            paymentDate: db.orderPayments?.[o.id]?.date || null
        };
    });

    return NextResponse.json(billableOrders);
}

export async function POST(request: Request) {
    const currentUser = await getSessionUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager', 'clerk'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    try {
        const body = await request.json();
        const { orderId, action } = body;
        const db = await readDb();

        const orderIndex = db.orders.findIndex((o: any) => o.id === orderId);
        if (orderIndex === -1) return NextResponse.json({ error: 'Order not found' }, { status: 404 });

        if (!db.orderPayments) db.orderPayments = {};

        if (action === 'mark_paid') {
            db.orderPayments[orderId] = {
                status: 'Paid',
                date: new Date().toISOString()
            };
        }

        await writeDb(db);
        return NextResponse.json({ message: 'Updated' });
    } catch (error) {
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}
