import { NextResponse } from 'next/server';
import { db } from '@/db';
import { retentionPolicies } from '@/db/schema';
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

// PUT /api/retention/[id]
export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (currentUser.role !== 'admin') {
        return NextResponse.json({ error: 'Forbidden — admin only' }, { status: 403 });
    }

    try {
        const { id } = await params;
        const body = await request.json();
        const { specimenType, retentionDays, temperature, disposalMethod, notes, active } = body;

        const existing = await db.select().from(retentionPolicies).where(eq(retentionPolicies.id, id)).limit(1);
        if (!existing.length) return NextResponse.json({ error: 'Not found' }, { status: 404 });

        const updates: Partial<typeof retentionPolicies.$inferInsert> = {};
        if (specimenType !== undefined) updates.specimenType = specimenType;
        if (retentionDays !== undefined) updates.retentionDays = Number(retentionDays);
        if (temperature !== undefined) updates.temperature = temperature;
        if (disposalMethod !== undefined) updates.disposalMethod = disposalMethod;
        if (notes !== undefined) updates.notes = notes;
        if (active !== undefined) updates.active = active;

        await db.update(retentionPolicies).set(updates).where(eq(retentionPolicies.id, id));
        const updated = await db.select().from(retentionPolicies).where(eq(retentionPolicies.id, id)).limit(1);
        return NextResponse.json(updated[0]);
    } catch (error) {
        console.error('PUT /api/retention/[id] error:', error);
        return NextResponse.json({ error: 'Failed to update retention policy' }, { status: 500 });
    }
}

// DELETE /api/retention/[id]
export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (currentUser.role !== 'admin') {
        return NextResponse.json({ error: 'Forbidden — admin only' }, { status: 403 });
    }

    try {
        const { id } = await params;
        const existing = await db.select().from(retentionPolicies).where(eq(retentionPolicies.id, id)).limit(1);
        if (!existing.length) return NextResponse.json({ error: 'Not found' }, { status: 404 });

        await db.delete(retentionPolicies).where(eq(retentionPolicies.id, id));
        return NextResponse.json({ success: true });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to delete retention policy' }, { status: 500 });
    }
}
