import { NextResponse } from 'next/server';
import { db } from '@/db';
import { deltaCheckRules } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';

async function getCurrentUser() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return null;
    try {
        return JSON.parse(session.value);
    } catch {
        return null;
    }
}

// PUT /api/delta-checks/rules/[id] — update a rule
export async function PUT(
    request: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden: Manager/Admin only' }, { status: 403 });
    }

    try {
        const { id } = await params;
        const body = await request.json();
        const { testId, testCode, deltaType, threshold, direction, enabled } = body;

        const existing = await db.select().from(deltaCheckRules).where(eq(deltaCheckRules.id, id)).limit(1);
        if (existing.length === 0) {
            return NextResponse.json({ error: 'Rule not found' }, { status: 404 });
        }

        const updates: Record<string, unknown> = {};
        if (testId !== undefined) updates.testId = testId;
        if (testCode !== undefined) updates.testCode = testCode;
        if (deltaType !== undefined) updates.deltaType = deltaType;
        if (threshold !== undefined) updates.threshold = Number(threshold);
        if (direction !== undefined) updates.direction = direction;
        if (enabled !== undefined) updates.enabled = enabled;

        await db.update(deltaCheckRules).set(updates).where(eq(deltaCheckRules.id, id));

        const updated = await db.select().from(deltaCheckRules).where(eq(deltaCheckRules.id, id)).limit(1);
        return NextResponse.json(updated[0]);
    } catch (error) {
        console.error('PUT delta-check rule error:', error);
        return NextResponse.json({ error: 'Failed to update delta check rule' }, { status: 500 });
    }
}

// DELETE /api/delta-checks/rules/[id] — delete a rule
export async function DELETE(
    request: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden: Manager/Admin only' }, { status: 403 });
    }

    try {
        const { id } = await params;
        const existing = await db.select().from(deltaCheckRules).where(eq(deltaCheckRules.id, id)).limit(1);
        if (existing.length === 0) {
            return NextResponse.json({ error: 'Rule not found' }, { status: 404 });
        }

        await db.delete(deltaCheckRules).where(eq(deltaCheckRules.id, id));
        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('DELETE delta-check rule error:', error);
        return NextResponse.json({ error: 'Failed to delete delta check rule' }, { status: 500 });
    }
}
