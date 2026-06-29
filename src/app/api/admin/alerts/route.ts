import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { cookies } from 'next/headers';
import { db } from '@/db';
import { sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';

// Helper to get authenticated user from token
async function getAuthenticatedUser() {
    const cookieStore = await cookies();
    const token = cookieStore.get('auth_token')?.value;

    if (!token) return null;

    const sessionResult = await db.select()
        .from(sessions)
        .where(eq(sessions.token, token))
        .limit(1);

    const session = sessionResult[0];
    if (!session || session.expiresAt < Date.now()) return null;

    const userResult = await db.select()
        .from(users)
        .where(eq(users.id, session.userId))
        .limit(1);

    return userResult[0] || null;
}

export async function GET() {
    const user = await getAuthenticatedUser();
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(user.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

    const dbData = await readDb();
    // Return all alerts, sorted by date desc
    const alerts = (dbData.systemAlerts || []).sort((a: any, b: any) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    return NextResponse.json(alerts);
}

export async function POST(request: Request) {
    const user = await getAuthenticatedUser();
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(user.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

    try {
        const { message, type } = await request.json();
        const dbData = await readDb();
        if (!dbData.systemAlerts) dbData.systemAlerts = [];

        const newAlert = {
            id: `alert-${Date.now()}`,
            message,
            type: type || 'info', // info, warning, error
            createdAt: new Date().toISOString(),
            active: true,
            timeout: null, // Default to null (no auto-dismiss)
            readBy: []
        };

        dbData.systemAlerts.push(newAlert);
        await logAudit(dbData, 'Alert', newAlert.id, 'CREATE', null, newAlert, user.username);
        await writeDb(dbData);

        return NextResponse.json(newAlert);
    } catch (e) {
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}

export async function PUT(request: Request) {
    // Toggle Active Status
    const user = await getAuthenticatedUser();
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(user.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

    try {
        const { id, active } = await request.json();
        const dbData = await readDb();
        const alert = dbData.systemAlerts.find((a: any) => a.id === id);
        if (alert) {
            alert.active = active;
            await logAudit(dbData, 'Alert', id, 'UPDATE', null, { active }, user.username);
            await writeDb(dbData);
            return NextResponse.json({ success: true });
        }
        return NextResponse.json({ error: 'Not found' }, { status: 404 });
    } catch (e) { return NextResponse.json({ error: 'Failed' }, { status: 500 }); }
}

