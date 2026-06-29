import { NextResponse } from 'next/server';
import { db } from '@/db';
import { demographicReferenceRanges } from '@/db/schema';
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

// PUT /api/demographic-ranges/[id]
export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { id } = await params;
        const body = await request.json();

        const existing = await db.select().from(demographicReferenceRanges).where(eq(demographicReferenceRanges.id, id)).limit(1);
        if (!existing.length) return NextResponse.json({ error: 'Not found' }, { status: 404 });

        const updates: Partial<typeof demographicReferenceRanges.$inferInsert> = {};
        const fields = ['testId', 'testCode', 'ageMin', 'ageMax', 'gender', 'pregnancy', 'trimester',
            'lowNormal', 'highNormal', 'lowCritical', 'highCritical', 'unit', 'notes', 'active'] as const;

        for (const field of fields) {
            if (body[field] !== undefined) {
                (updates as any)[field] = body[field];
            }
        }

        await db.update(demographicReferenceRanges).set(updates).where(eq(demographicReferenceRanges.id, id));
        const updated = await db.select().from(demographicReferenceRanges).where(eq(demographicReferenceRanges.id, id)).limit(1);
        return NextResponse.json(updated[0]);
    } catch (error) {
        console.error('PUT /api/demographic-ranges/[id] error:', error);
        return NextResponse.json({ error: 'Failed to update range' }, { status: 500 });
    }
}

// DELETE /api/demographic-ranges/[id]
export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { id } = await params;
        const existing = await db.select().from(demographicReferenceRanges).where(eq(demographicReferenceRanges.id, id)).limit(1);
        if (!existing.length) return NextResponse.json({ error: 'Not found' }, { status: 404 });

        await db.delete(demographicReferenceRanges).where(eq(demographicReferenceRanges.id, id));
        return NextResponse.json({ success: true });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to delete range' }, { status: 500 });
    }
}
