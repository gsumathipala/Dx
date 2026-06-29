import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { cookies } from 'next/headers';

export async function GET() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');

    // Public alerts if no session? Or active always?
    // Let's assume generic alerts are visible, but acknowledgment requires user.
    // If no user, just return all active.

    let username = 'guest';
    if (session) {
        try {
            const user = JSON.parse(session.value);
            username = user.username;
        } catch (e) { }
    }

    const db = await readDb();
    const activeAlerts = (db.systemAlerts || [])
        .filter((a: any) => a.active)
        .filter((a: any) => !a.readBy.includes(username));

    return NextResponse.json(activeAlerts);
}

export async function POST(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const user = JSON.parse(session.value);
    const { id } = await request.json();

    const db = await readDb();
    const alertIndex = db.systemAlerts.findIndex((a: any) => a.id === id);

    if (alertIndex !== -1) {
        if (!db.systemAlerts[alertIndex].readBy.includes(user.username)) {
            db.systemAlerts[alertIndex].readBy.push(user.username);
            await writeDb(db);
        }
    }

    return NextResponse.json({ success: true });
}
