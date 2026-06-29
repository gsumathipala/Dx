import { NextResponse } from 'next/server';
import { readDb } from '@/lib/db';
import { cookies } from 'next/headers';

export async function GET() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const db = await readDb();
        // Return only ACTIVE alerts
        const alerts = (db.systemAlerts || [])
            .filter((a: any) => a.active)
            .sort((a: any, b: any) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

        return NextResponse.json(alerts);
    } catch (error) {
        return NextResponse.json({ error: 'Failed to fetch alerts' }, { status: 500 });
    }
}
