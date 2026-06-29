import { NextResponse } from 'next/server';
import { db } from '@/db';
import { reflexRules, testDefinitions } from '@/db/schema';
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

// PUT /api/reflex-rules/[id] — update a reflex rule
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
        const { name, triggerTestId, triggerCondition, addTestId, enabled } = body;

        const existing = await db.select().from(reflexRules).where(eq(reflexRules.id, id)).limit(1);
        if (existing.length === 0) {
            return NextResponse.json({ error: 'Rule not found' }, { status: 404 });
        }

        const updates: Record<string, unknown> = {};
        if (name !== undefined) updates.name = name;
        if (triggerTestId !== undefined) updates.triggerTestId = triggerTestId;
        if (triggerCondition !== undefined) {
            updates.triggerCondition = typeof triggerCondition === 'string'
                ? triggerCondition
                : JSON.stringify(triggerCondition);
        }
        if (addTestId !== undefined) {
            updates.addTestId = addTestId;
            // Update addTestCode from DB
            const addTestRows = await db.select().from(testDefinitions).where(eq(testDefinitions.id, addTestId)).limit(1);
            if (addTestRows.length > 0) {
                updates.addTestCode = addTestRows[0].code;
            }
        }
        if (enabled !== undefined) updates.enabled = enabled;

        await db.update(reflexRules).set(updates).where(eq(reflexRules.id, id));

        const updated = await db.select().from(reflexRules).where(eq(reflexRules.id, id)).limit(1);
        return NextResponse.json(updated[0]);
    } catch (error) {
        console.error('PUT reflex-rule error:', error);
        return NextResponse.json({ error: 'Failed to update reflex rule' }, { status: 500 });
    }
}

// DELETE /api/reflex-rules/[id] — delete a reflex rule
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
        const existing = await db.select().from(reflexRules).where(eq(reflexRules.id, id)).limit(1);
        if (existing.length === 0) {
            return NextResponse.json({ error: 'Rule not found' }, { status: 404 });
        }

        await db.delete(reflexRules).where(eq(reflexRules.id, id));
        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('DELETE reflex-rule error:', error);
        return NextResponse.json({ error: 'Failed to delete reflex rule' }, { status: 500 });
    }
}
