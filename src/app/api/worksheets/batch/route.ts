
import { NextResponse } from 'next/server';
import { db } from '@/db';
import { orders, results, testDefinitions } from '@/db/schema';
import { eq, and, inArray } from 'drizzle-orm';
import { getAuthUser } from '@/lib/auth';

// Fetch pending tests for a specific department (e.g., Hematology)
export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const department = searchParams.get('department') || 'Hematology';

    try {
        // 1. Get tests for this dept
        const deptTests = await db.select().from(testDefinitions).where(eq(testDefinitions.department, department));
        const testCodes = deptTests.map(t => t.code); // Assuming code matches testId usage

        if (!testCodes.length) return NextResponse.json([]);

        // 2. Get Pending Orders (Naive linear scan of JSON strings for now, or use SQL LIKE in real app)
        // For efficiency, let's just fetch recent orders and filter in memory for this MVP
        const activeOrders = await db.select().from(orders).where(
            inArray(orders.status, ['In Progress', 'Pending', 'Accessioned'])
        );

        const workstationLoad = activeOrders.filter(o => {
            const tIds = JSON.parse(o.testIds || '[]');
            // Check if any test in this order belongs to the department
            return tIds.some((tid: string) => testCodes.includes(tid));
        }).map(o => ({
            orderId: o.id,
            accessionNumber: o.accessionNumber,
            tests: JSON.parse(o.testIds || '[]').filter((tid: string) => testCodes.includes(tid))
        }));

        return NextResponse.json(workstationLoad);

    } catch (e: any) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
