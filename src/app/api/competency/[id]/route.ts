import { NextResponse } from 'next/server';
import { db } from '@/db';
import { userCompetencies } from '@/db/schema';
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

// PUT /api/competency/[id]
export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { id } = await params;
        const body = await request.json();
        const { testId, category, competencyDate, expiryDate, status, notes } = body;

        const existing = await db.select().from(userCompetencies).where(eq(userCompetencies.id, id)).limit(1);
        if (!existing.length) return NextResponse.json({ error: 'Not found' }, { status: 404 });

        const updates: Partial<typeof userCompetencies.$inferInsert> = {};
        if (testId !== undefined) updates.testId = testId;
        if (category !== undefined) updates.category = category;
        if (competencyDate !== undefined) updates.competencyDate = competencyDate;
        if (expiryDate !== undefined) updates.expiryDate = expiryDate;
        if (status !== undefined) updates.status = status;
        if (notes !== undefined) updates.notes = notes;

        await db.update(userCompetencies).set(updates).where(eq(userCompetencies.id, id));
        const updated = await db.select().from(userCompetencies).where(eq(userCompetencies.id, id)).limit(1);
        return NextResponse.json(updated[0]);
    } catch (error) {
        console.error('PUT /api/competency/[id] error:', error);
        return NextResponse.json({ error: 'Failed to update competency record' }, { status: 500 });
    }
}

// DELETE /api/competency/[id]
export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { id } = await params;
        const existing = await db.select().from(userCompetencies).where(eq(userCompetencies.id, id)).limit(1);
        if (!existing.length) return NextResponse.json({ error: 'Not found' }, { status: 404 });

        await db.delete(userCompetencies).where(eq(userCompetencies.id, id));
        return NextResponse.json({ success: true });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to delete competency record' }, { status: 500 });
    }
}
