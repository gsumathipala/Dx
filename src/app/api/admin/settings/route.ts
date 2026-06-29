import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { cookies } from 'next/headers';

async function getSessionUser() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return null;
    try { return JSON.parse(session.value); } catch { return null; }
}

export async function GET() {
    const currentUser = await getSessionUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    const db = await readDb();
    return NextResponse.json(db.settings || {});
}

export async function POST(request: Request) {
    const currentUser = await getSessionUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const updates = await request.json();
        const db = await readDb();

        const oldSettings = { ...db.settings };
        db.settings = { ...oldSettings, ...updates };

        await logAudit(db, 'Settings', 'Global', 'UPDATE', oldSettings, db.settings, currentUser.username);
        await writeDb(db);

        return NextResponse.json(db.settings);
    } catch (e) {
        return NextResponse.json({ error: 'Failed to update settings' }, { status: 500 });
    }
}
