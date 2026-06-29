import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { cookies } from 'next/headers';
import { getAuthUser } from '@/lib/auth';

export async function GET() {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const db = await readDb();
    return NextResponse.json(db.manualSections || []);
}

export async function POST(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const currentUser = JSON.parse(session.value);
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const newSections = await request.json();
        const db = await readDb();

        // Validate structure briefly?
        if (!Array.isArray(newSections)) throw new Error('Invalid format');

        db.manualSections = newSections;
        await logAudit(db, 'ManualSection', 'Sections', 'UPDATE', null, null, currentUser.username);

        await writeDb(db);
        return NextResponse.json({ success: true });
    } catch (e) {
        return NextResponse.json({ error: 'Failed to update manual' }, { status: 500 });
    }
}
