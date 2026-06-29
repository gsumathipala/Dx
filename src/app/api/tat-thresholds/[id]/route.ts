import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import { db } from '@/db';
import { tatThresholds, sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';

async function getAuthenticatedUser() {
    const cookieStore = await cookies();
    const token = cookieStore.get('auth_token')?.value;
    if (!token) return null;
    const sessionResult = await db.select().from(sessions).where(eq(sessions.token, token)).limit(1);
    const session = sessionResult[0];
    if (!session || session.expiresAt < Date.now()) return null;
    const userResult = await db.select().from(users).where(eq(users.id, session.userId)).limit(1);
    return userResult[0] || null;
}

function requireManagerOrAdmin(role: string) {
    return ['manager', 'admin', 'labmanager', 'supervisor'].includes(role?.toLowerCase());
}

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        if (!requireManagerOrAdmin(currentUser.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

        const { id } = await params;
        const body = await request.json();
        const updates: Record<string, unknown> = {};

        if (body.scope !== undefined) updates.scope = body.scope;
        if (body.scopeId !== undefined) updates.scopeId = body.scopeId;
        if (body.targetHours !== undefined) updates.targetHours = Number(body.targetHours);
        if (body.warningHours !== undefined) updates.warningHours = Number(body.warningHours);
        if (body.breachHours !== undefined) updates.breachHours = Number(body.breachHours);
        if (body.priority !== undefined) updates.priority = body.priority;
        if (body.active !== undefined) updates.active = body.active;

        await db.update(tatThresholds).set(updates).where(eq(tatThresholds.id, id));
        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('PUT /api/tat-thresholds/[id] error:', error);
        return NextResponse.json({ error: 'Failed to update TAT threshold', details: String(error) }, { status: 500 });
    }
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        if (!requireManagerOrAdmin(currentUser.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

        const { id } = await params;
        await db.delete(tatThresholds).where(eq(tatThresholds.id, id));
        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('DELETE /api/tat-thresholds/[id] error:', error);
        return NextResponse.json({ error: 'Failed to delete TAT threshold', details: String(error) }, { status: 500 });
    }
}
