import { NextResponse } from 'next/server';
import { readDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET() {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const db = await readDb();
    const orders = db.orders || [];

    // 1. Current Pending Volume
    const pending = orders.filter((o: any) => o.status !== 'Completed').length;
    const completed = orders.filter((o: any) => o.status === 'Completed').length;

    // 2. TAT Calculation (Completed Orders)
    let totalTatMinutes = 0;
    let tatCount = 0;

    // 3. Department Breakdown
    const deptCounts: Record<string, number> = { 'Chemistry': 0, 'Hematology': 0, 'Microbiology': 0 };

    orders.forEach((o: any) => {
        // TAT
        if (o.status === 'Completed') {
            // Find result for timestamp
            const result = db.results.find((r: any) => r.orderId === o.id);
            if (result) {
                const start = new Date(o.timestamp).getTime();
                const end = new Date(result.timestamp).getTime();
                const minutes = (end - start) / 1000 / 60;
                if (minutes > 0 && minutes < 10000) { // Sanity check
                    totalTatMinutes += minutes;
                    tatCount++;
                }
            }
        }

        // Depts (Simulated based on test ID)
        (o.testIds || []).forEach((tId: string) => {
            if (['WBC', 'RBC', 'PLT', 'CBC'].some(s => tId.includes(s))) deptCounts['Hematology']++;
            else if (tId.includes('CULT')) deptCounts['Microbiology']++;
            else deptCounts['Chemistry']++;
        });
    });

    const avgTat = tatCount > 0 ? Math.round(totalTatMinutes / tatCount) : 0;

    return NextResponse.json({
        pending,
        completed,
        avgTat,
        deptCounts
    });
}
