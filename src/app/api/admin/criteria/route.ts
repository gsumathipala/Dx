import { NextResponse } from 'next/server';
import { db } from '@/db';
import { rejectionCriteria } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

async function getUser() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return null;
    try { return JSON.parse(session.value); } catch { return null; }
}

export async function GET() {
    const user = await getUser();
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const data = await db.select().from(rejectionCriteria);
    return NextResponse.json(data);
}

export async function POST(request: Request) {
    const user = await getUser();
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(user.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { criterion } = await request.json();
        if (!criterion) return NextResponse.json({ error: 'criterion is required' }, { status: 400 });

        // Avoid duplicates
        const existing = await db.select({ id: rejectionCriteria.id })
            .from(rejectionCriteria)
            .where(eq(rejectionCriteria.reason, String(criterion)))
            .limit(1);

        if (!existing.length) {
            await db.insert(rejectionCriteria).values({
                id: uuidv4(),
                reason: String(criterion),
                category: 'General',
                active: true
            });
        }

        return NextResponse.json({ success: true });
    } catch (e) {
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}

export async function DELETE(request: Request) {
    const user = await getUser();
    if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(user.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { criterion } = await request.json();
        if (!criterion) return NextResponse.json({ error: 'criterion is required' }, { status: 400 });
        await db.delete(rejectionCriteria).where(eq(rejectionCriteria.reason, String(criterion)));
        return NextResponse.json({ success: true });
    } catch (e) {
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}
