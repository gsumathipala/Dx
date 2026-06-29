import { NextResponse } from 'next/server';
import { db } from '@/db';
import { notifiableConditions } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';

async function requireAdmin() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return null;
    const user = JSON.parse(session.value);
    if (!['admin', 'manager'].includes(user.role)) return null;
    return user;
}

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const user = await requireAdmin();
    if (!user) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    const { id } = await params;
    try {
        const body = await request.json();
        const update: any = {};
        if (body.name !== undefined) update.name = body.name;
        if (body.organism !== undefined) update.organism = body.organism;
        if (body.testIds !== undefined) update.testIds = JSON.stringify(body.testIds);
        if (body.reportingBody !== undefined) update.reportingBody = body.reportingBody;
        if (body.timeframe !== undefined) update.timeframe = body.timeframe;
        if (body.active !== undefined) update.active = body.active;
        await db.update(notifiableConditions).set(update).where(eq(notifiableConditions.id, id));
        return NextResponse.json({ success: true });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to update' }, { status: 500 });
    }
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
    const user = await requireAdmin();
    if (!user) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    const { id } = await params;
    try {
        await db.delete(notifiableConditions).where(eq(notifiableConditions.id, id));
        return NextResponse.json({ success: true });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to delete' }, { status: 500 });
    }
}
