import { NextResponse } from 'next/server';
import { db } from '@/db';
import { orders, testDefinitions, criticalValueNotifications } from '@/db/schema';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const department = searchParams.get('department');
    const today = new Date().toISOString().split('T')[0];

    try {
        const [allOrders, allTests, allNotifications] = await Promise.all([
            db.select().from(orders),
            db.select().from(testDefinitions),
            db.select().from(criticalValueNotifications)
        ]);

        const testDeptMap = new Map(allTests.map(t => [t.id, t.department]));

        const belongsToDept = (order: typeof allOrders[0]) => {
            if (!department || department === 'ALL') return true;
            try {
                const ids: string[] = JSON.parse(order.testIds || '[]');
                return ids.some(tid => testDeptMap.get(tid) === department);
            } catch { return false; }
        };

        // 1. Pending — any non-completed status
        const pending = allOrders.filter(o =>
            o.status !== 'Completed' && belongsToDept(o)
        ).length;

        // 2. Completed today
        const completed = allOrders.filter(o =>
            o.status === 'Completed' &&
            (o.completedAt?.startsWith(today) || o.timestamp?.startsWith(today)) &&
            belongsToDept(o)
        ).length;

        // 3. Critical results — pending (unacknowledged) critical value notifications
        const critical = allNotifications.filter(n => {
            if (n.status !== 'Pending') return false;
            if (!department || department === 'ALL') return true;
            return testDeptMap.get(n.testId) === department;
        }).length;

        // 4. Avg TAT for completed orders (use timestamp as start, completedAt as end)
        const completedWithDates = allOrders.filter(o =>
            o.status === 'Completed' && o.completedAt && o.timestamp && belongsToDept(o)
        );

        let totalHours = 0;
        let tatCount = 0;
        for (const o of completedWithDates) {
            const hours = (new Date(o.completedAt!).getTime() - new Date(o.timestamp).getTime()) / 3_600_000;
            if (hours > 0 && hours < 720) { // ignore implausible values (>30 days)
                totalHours += hours;
                tatCount++;
            }
        }
        const avgTat = tatCount > 0 ? (totalHours / tatCount).toFixed(1) : '0';

        return NextResponse.json({ pending, completed, critical, tat: `${avgTat}h` });
    } catch (error) {
        console.error('Stats error:', error);
        return NextResponse.json({ pending: 0, completed: 0, critical: 0, tat: '0h' });
    }
}
