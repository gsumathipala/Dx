import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import { db } from '@/db';
import { phlebotomySchedules, sessions, users } from '@/db/schema';
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

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const { id } = await params;
        const body = await request.json();
        const updates: Record<string, unknown> = {};

        const validStatuses = ['Scheduled', 'InProgress', 'Completed', 'Cancelled'];
        if (body.status !== undefined) {
            if (!validStatuses.includes(body.status)) {
                return NextResponse.json({ error: `Invalid status. Must be one of: ${validStatuses.join(', ')}` }, { status: 400 });
            }
            updates.status = body.status;
            if (body.status === 'Completed') {
                updates.completedAt = new Date().toISOString();
            }
        }

        if (body.assignedTo !== undefined) updates.assignedTo = body.assignedTo;
        if (body.notes !== undefined) updates.notes = body.notes;
        if (body.scheduledAt !== undefined) updates.scheduledAt = body.scheduledAt;
        if (body.wardLocation !== undefined) updates.wardLocation = body.wardLocation;

        await db.update(phlebotomySchedules).set(updates).where(eq(phlebotomySchedules.id, id));
        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('PUT /api/phlebotomy/[id] error:', error);
        return NextResponse.json({ error: 'Failed to update phlebotomy schedule', details: String(error) }, { status: 500 });
    }
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const { id } = await params;
        // Cancel rather than hard-delete for audit trail
        await db.update(phlebotomySchedules)
            .set({ status: 'Cancelled' })
            .where(eq(phlebotomySchedules.id, id));

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('DELETE /api/phlebotomy/[id] error:', error);
        return NextResponse.json({ error: 'Failed to cancel phlebotomy schedule', details: String(error) }, { status: 500 });
    }
}
