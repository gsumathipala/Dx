import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import { db } from '@/db';
import { orders, patients, tatThresholds } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { getAuthUser } from '@/lib/auth';

export async function GET() {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const now = new Date();
        const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

        const allOrders = await db.select().from(orders);
        const allPatients = await db.select().from(patients);
        const allThresholds = await db.select().from(tatThresholds);

        const patientMap = new Map(allPatients.map(p => [p.id, p]));

        // Helper: find best matching threshold for an order
        function findThreshold(order: typeof allOrders[0]) {
            const priority = order.priority || 'Routine';
            // For now: test-level and department scope require scopeId matching;
            // without test/dept metadata on the order itself we fall through to global.
            // Test-level: scope='test', scopeId matches a testId in order.testIds
            let testIds: string[] = [];
            try { testIds = JSON.parse(order.testIds || '[]'); } catch { testIds = []; }

            const priorityThresholds = allThresholds.filter(t => t.active && (t.priority === priority || t.priority === 'Routine'));

            // 1. Test-level
            const testLevel = priorityThresholds.find(t => t.scope === 'test' && t.scopeId && testIds.includes(t.scopeId));
            if (testLevel) return testLevel;

            // 2. Department-level (no department on order, skip)

            // 3. Global
            const global = priorityThresholds.find(t => t.scope === 'global');
            if (global) return global;

            return null;
        }

        const results: {
            orderId: string;
            accessionNumber: string;
            patientName: string;
            hoursOpen: number;
            targetHours: number | null;
            warningHours: number | null;
            breachHours: number | null;
            status: 'ok' | 'warning' | 'breach';
            isCompleted: boolean;
        }[] = [];

        for (const order of allOrders) {
            const isCompleted = order.status === 'Completed';
            const orderTime = new Date(order.timestamp);

            // Skip completed orders older than 7 days
            if (isCompleted && orderTime < sevenDaysAgo) continue;

            const endTime = isCompleted && order.completedAt ? new Date(order.completedAt) : now;
            const hoursOpen = (endTime.getTime() - orderTime.getTime()) / (1000 * 60 * 60);

            const patient = patientMap.get(order.patientId);
            const patientName = patient ? `${patient.firstName} ${patient.lastName}` : 'Unknown';

            const threshold = findThreshold(order);

            let tatStatus: 'ok' | 'warning' | 'breach' = 'ok';
            if (threshold) {
                if (hoursOpen >= threshold.breachHours) {
                    tatStatus = 'breach';
                } else if (hoursOpen >= threshold.warningHours) {
                    tatStatus = 'warning';
                }
            }

            results.push({
                orderId: order.id,
                accessionNumber: order.accessionNumber,
                patientName,
                hoursOpen: Math.round(hoursOpen * 100) / 100,
                targetHours: threshold?.targetHours ?? null,
                warningHours: threshold?.warningHours ?? null,
                breachHours: threshold?.breachHours ?? null,
                status: tatStatus,
                isCompleted,
            });
        }

        // Sort: breaches first, then warnings, then ok
        const statusOrder = { breach: 0, warning: 1, ok: 2 };
        results.sort((a, b) => statusOrder[a.status] - statusOrder[b.status] || b.hoursOpen - a.hoursOpen);

        return NextResponse.json(results);
    } catch (error) {
        console.error('GET /api/tat-monitor error:', error);
        return NextResponse.json({ error: 'Failed to calculate TAT', details: String(error) }, { status: 500 });
    }
}
