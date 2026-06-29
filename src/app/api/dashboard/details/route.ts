import { NextResponse } from 'next/server';
import { readDb } from '@/lib/db';
import { db } from '@/db';
import { criticalValueNotifications } from '@/db/schema';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const type = searchParams.get('type');
    const department = searchParams.get('department');
    const dbData = await readDb();

    // Map Tests to Departments and Names
    const testDeptMap = new Map();
    const testNameMap = new Map();
    (dbData.testDefinitions || []).forEach((t: any) => {
        testDeptMap.set(t.id, t.department);
        testNameMap.set(t.id, t.name);
    });

    const belongsToDept = (order: any) => {
        if (!department || department === 'ALL') return true;
        if (!order.testIds || !Array.isArray(order.testIds)) return false;
        return order.testIds.some((tid: string) => testDeptMap.get(tid) === department);
    };

    let data: any[] = [];
    const today = new Date().toISOString().split('T')[0];

    if (type === 'PENDING') {
        data = (dbData.orders || [])
            .filter((o: any) => o.status !== 'Completed' && belongsToDept(o))
            .map((o: any) => enrichOrder(o, dbData, testNameMap));
    }
    else if (type === 'COMPLETED') {
        data = (dbData.orders || [])
            .filter((o: any) =>
                o.status === 'Completed' &&
                (o.completedAt?.startsWith(today) || o.timestamp?.startsWith(today)) &&
                belongsToDept(o))
            .map((o: any) => enrichOrder(o, dbData, testNameMap));
    }
    else if (type === 'CRITICAL') {
        // Source of truth: critical value notifications written by the clinical engine
        const notifications = await db.select().from(criticalValueNotifications);
        data = notifications
            .filter((n) => {
                if (!department || department === 'ALL') return true;
                return testDeptMap.get(n.testId) === department;
            })
            .map((n) => {
                const order = (dbData.orders || []).find((o: any) => o.id === n.orderId);
                const patient = (dbData.patients || []).find((p: any) => p.id === n.patientId);
                return {
                    id: n.id,
                    testName: testNameMap.get(n.testId) || n.testCode || n.testId,
                    value: n.value,
                    flag: `CRITICAL ${n.criticalType}`,
                    status: n.status,
                    accessionNumber: order?.accessionNumber || '',
                    patientName: patient ? `${patient.firstName} ${patient.lastName}` : 'Unknown',
                    timestamp: n.createdAt
                };
            })
            .sort((a, b) => (b.timestamp > a.timestamp ? 1 : -1));
    }
    else if (type === 'TAT') {
        // Show recent completed with TAT (timestamp = order time, completedAt = finish)
        data = (dbData.orders || [])
            .filter((o: any) => o.status === 'Completed' && o.completedAt && o.timestamp && belongsToDept(o))
            .map((o: any) => {
                const start = new Date(o.timestamp).getTime();
                const end = new Date(o.completedAt).getTime();
                const hours = ((end - start) / (1000 * 60 * 60)).toFixed(1);
                return {
                    ...enrichOrder(o, dbData, testNameMap),
                    tatHours: hours
                };
            })
            .sort((a: any, b: any) => new Date(b.completedAt).getTime() - new Date(a.completedAt).getTime())
            .slice(0, 50);
    }

    return NextResponse.json(data);
}

function enrichOrder(order: any, dbData: any, testNameMap: Map<string, string>) {
    const patient = (dbData.patients || []).find((p: any) => p.id === order.patientId);
    const testNames = (order.testIds || [])
        .map((tid: string) => testNameMap.get(tid) || tid)
        .join(', ');
    return {
        id: order.id,
        accessionNumber: order.accessionNumber,
        patientName: patient ? `${patient.firstName} ${patient.lastName}` : 'Unknown',
        mrn: patient?.mrn || 'N/A',
        tests: testNames,
        status: order.status,
        priority: order.priority,
        createdAt: order.timestamp,
        completedAt: order.completedAt
    };
}
