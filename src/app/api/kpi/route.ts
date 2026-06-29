import { NextResponse } from 'next/server';
import { db } from '@/db';
import { orders, results, testDefinitions, specimenReceiving } from '@/db/schema';
import { gte, sql } from 'drizzle-orm';
import { cookies } from 'next/headers';

export async function GET(request: Request) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const { searchParams } = new URL(request.url);
        const days = parseInt(searchParams.get('days') ?? '30', 10);

        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - days);
        const cutoffStr = cutoff.toISOString();

        // Fetch all orders in range
        const allOrders = await db
            .select()
            .from(orders)
            .where(gte(orders.timestamp, cutoffStr));

        const totalOrders = allOrders.length;
        const completedOrders = allOrders.filter((o) => o.status === 'Completed');
        const statOrders = allOrders.filter((o) => o.priority === 'STAT' || o.priority === 'Stat').length;

        // Volume by day
        const volumeByDayMap = new Map<string, number>();
        for (const o of allOrders) {
            const day = o.timestamp.substring(0, 10);
            volumeByDayMap.set(day, (volumeByDayMap.get(day) ?? 0) + 1);
        }
        const volumeByDay = Array.from(volumeByDayMap.entries())
            .map(([date, count]) => ({ date, count }))
            .sort((a, b) => a.date.localeCompare(b.date));

        // Fetch all test definitions for dept mapping
        const allTestDefs = await db.select().from(testDefinitions);
        const testDefMap = new Map(allTestDefs.map((td) => [td.id, td]));

        // Volume by department (completed orders, using first test's department)
        const deptCountMap = new Map<string, number>();
        for (const o of completedOrders) {
            let dept = 'Unknown';
            if (o.testIds) {
                try {
                    const ids: string[] = JSON.parse(o.testIds);
                    if (ids.length > 0) {
                        const td = testDefMap.get(ids[0]);
                        if (td) dept = td.department;
                    }
                } catch {
                    // ignore
                }
            }
            deptCountMap.set(dept, (deptCountMap.get(dept) ?? 0) + 1);
        }
        const volumeByDepartment = Array.from(deptCountMap.entries()).map(([department, count]) => ({
            department,
            count,
        }));

        // TAT compliance: % of completed orders finished within tatHours
        let tatCompliantCount = 0;
        let tatTotalCount = 0;
        const deptTatMap = new Map<string, { compliant: number; total: number }>();

        for (const o of completedOrders) {
            if (!o.completedAt || !o.timestamp) continue;
            const startMs = new Date(o.timestamp).getTime();
            const endMs = new Date(o.completedAt).getTime();
            const actualHours = (endMs - startMs) / 3600000;

            let dept = 'Unknown';
            let targetHours: number | null = null;

            if (o.testIds) {
                try {
                    const ids: string[] = JSON.parse(o.testIds);
                    if (ids.length > 0) {
                        const td = testDefMap.get(ids[0]);
                        if (td) {
                            dept = td.department;
                            targetHours = td.tatHours ?? null;
                        }
                    }
                } catch {
                    // ignore
                }
            }

            if (targetHours !== null) {
                tatTotalCount++;
                const compliant = actualHours <= targetHours;
                if (compliant) tatCompliantCount++;

                const cur = deptTatMap.get(dept) ?? { compliant: 0, total: 0 };
                deptTatMap.set(dept, {
                    compliant: cur.compliant + (compliant ? 1 : 0),
                    total: cur.total + 1,
                });
            }
        }

        const overallTatCompliance = tatTotalCount > 0 ? Math.round((tatCompliantCount / tatTotalCount) * 100) : 100;
        const byDepartment = Array.from(deptTatMap.entries()).map(([dept, { compliant, total }]) => ({
            dept,
            compliance: Math.round((compliant / total) * 100),
        }));

        // Avg TAT hours
        let totalTatHours = 0;
        let tatCountForAvg = 0;
        for (const o of completedOrders) {
            if (!o.completedAt || !o.timestamp) continue;
            const h = (new Date(o.completedAt).getTime() - new Date(o.timestamp).getTime()) / 3600000;
            totalTatHours += h;
            tatCountForAvg++;
        }
        const avgTatHours = tatCountForAvg > 0 ? Math.round((totalTatHours / tatCountForAvg) * 10) / 10 : 0;

        // Rejection rate from specimen_receiving
        const receivingRows = await db
            .select()
            .from(specimenReceiving)
            .where(gte(specimenReceiving.receivedAt, cutoffStr));
        const rejectedCount = receivingRows.filter((r) => r.status === 'Rejected').length;
        const rejectionRate = receivingRows.length > 0 ? Math.round((rejectedCount / receivingRows.length) * 1000) / 10 : 0;

        // Completion rate
        const completionRate = totalOrders > 0 ? Math.round((completedOrders.length / totalOrders) * 1000) / 10 : 0;

        // Critical results: results with 'C' flag
        const orderIdsInRange = allOrders.map((o) => o.id);
        let criticalResults = 0;
        if (orderIdsInRange.length > 0) {
            const CHUNK = 200;
            let critCount = 0;
            for (let i = 0; i < orderIdsInRange.length; i += CHUNK) {
                const chunk = orderIdsInRange.slice(i, i + CHUNK);
                const safeIds = chunk.map((id) => `'${id.replace(/'/g, "''")}'`).join(',');
                const rows = await db
                    .select({ resultFlags: results.resultFlags, orderId: results.orderId })
                    .from(results)
                    .where(sql.raw(`order_id IN (${safeIds})`));
                // Count unique orders with critical flags
                const critOrderIds = new Set<string>();
                for (const row of rows) {
                    if (!row.resultFlags || critOrderIds.has(row.orderId)) continue;
                    try {
                        const flags: string[] = JSON.parse(row.resultFlags);
                        if (flags.some((f) => f === 'C' || f === 'CH' || f === 'CL' || f === 'CritHigh' || f === 'CritLow')) {
                            critOrderIds.add(row.orderId);
                        }
                    } catch {
                        if (row.resultFlags.includes('C')) critOrderIds.add(row.orderId);
                    }
                }
                critCount += critOrderIds.size;
            }
            criticalResults = critCount;
        }

        // Top tests ordered
        const testCountMap = new Map<string, { code: string; count: number }>();
        for (const o of allOrders) {
            if (!o.testIds) continue;
            try {
                const ids: string[] = JSON.parse(o.testIds);
                for (const id of ids) {
                    const td = testDefMap.get(id);
                    const code = td?.code ?? id;
                    const cur = testCountMap.get(code) ?? { code, count: 0 };
                    testCountMap.set(code, { code, count: cur.count + 1 });
                }
            } catch {
                // ignore
            }
        }
        const topTests = Array.from(testCountMap.values())
            .sort((a, b) => b.count - a.count)
            .slice(0, 10)
            .map(({ code: testCode, count }) => ({ testCode, count }));

        return NextResponse.json({
            volumeByDay,
            volumeByDepartment,
            tatCompliance: {
                overall: overallTatCompliance,
                byDepartment,
            },
            rejectionRate,
            completionRate,
            avgTatHours,
            statOrders,
            criticalResults,
            topTests,
        });
    } catch (error) {
        console.error('KPI error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
