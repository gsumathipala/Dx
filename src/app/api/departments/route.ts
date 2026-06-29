import { NextResponse } from 'next/server';
import { readDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET() {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const db = await readDb();
        const tests = db.testDefinitions || [];

        // Get unique departments from tests
        // Also check users? No, tests define the lab capability usually.
        const depts = new Set<string>();
        tests.forEach((t: any) => {
            if (t.department) depts.add(t.department);
        });

        // Add standard ones if missing? Or just trust DB.
        // If DB is empty, maybe fallback?
        // Let's rely on DB.

        const sortedDepts = Array.from(depts).sort();
        return NextResponse.json(sortedDepts);
    } catch (error) {
        return NextResponse.json({ error: 'Failed to fetch departments' }, { status: 500 });
    }
}
