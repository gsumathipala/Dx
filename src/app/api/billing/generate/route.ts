import { NextResponse } from 'next/server';
import { db } from '@/db';
import { orders, invoices, billingItems } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { v4 as uuidv4 } from 'uuid';
import { getAuthUser } from '@/lib/auth';

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager', 'clerk'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    try {
        const body = await request.json();
        const { orderId } = body;

        // 1. Fetch Order and its tests
        const orderRes = await db.select().from(orders).where(eq(orders.id, orderId)).limit(1);
        if (!orderRes.length) {
            return NextResponse.json({ error: 'Order not found' }, { status: 404 });
        }
        const order = orderRes[0];

        let testIds: string[] = [];
        try {
            testIds = JSON.parse(order.testIds || '[]');
        } catch {
            testIds = [];
        }

        if (!testIds.length) {
            return NextResponse.json({ error: 'Order has no tests' }, { status: 400 });
        }

        // 2. Calculate Costs
        // In a real app, we would map testDefinition IDs to billing codes.
        // For this demo, we assume we have billingItems where code matches test code or ID.
        // OR simply sum up a base price.

        // Let's check for existing invoice first
        const existing = await db.select().from(invoices).where(eq(invoices.orderId, orderId));
        if (existing.length) {
            return NextResponse.json(existing[0]); // Return existing
        }

        // Calculate total (Simulator)
        // Ensure we have some default items in DB to test against, or hardcode fallback prices
        const billableItems = [];
        let total = 0;

        for (const testId of testIds) {
            // Try to find price
            const item = await db.select().from(billingItems).where(eq(billingItems.code, testId)).limit(1);
            if (item.length) {
                billableItems.push({
                    code: item[0].code,
                    description: item[0].name,
                    price: item[0].price
                });
                total += item[0].price;
            } else {
                // Fallback
                billableItems.push({
                    code: testId,
                    description: `Test execution (${testId})`,
                    price: 50.00
                });
                total += 50.00;
            }
        }

        // 3. Create Invoice
        const invoiceId = uuidv4();
        await db.insert(invoices).values({
            id: invoiceId,
            orderId: orderId,
            totalAmount: total,
            status: 'Pending',
            createdAt: new Date().toISOString(),
            items: JSON.stringify(billableItems)
        });

        return NextResponse.json({
            id: invoiceId,
            orderId,
            totalAmount: total,
            status: 'Pending',
            items: billableItems
        });

    } catch (e: any) {
        console.error('Billing error:', e);
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
