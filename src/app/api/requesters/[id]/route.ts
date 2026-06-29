import { NextResponse } from 'next/server';
import { db } from '@/db';
import { requesters } from '@/db/schema';
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

// GET /api/requesters/[id]
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { id } = await params;
        const rows = await db.select().from(requesters).where(eq(requesters.id, id)).limit(1);
        if (!rows.length) return NextResponse.json({ error: 'Not found' }, { status: 404 });
        return NextResponse.json(rows[0]);
    } catch (error) {
        return NextResponse.json({ error: 'Failed to fetch requester' }, { status: 500 });
    }
}

// PUT /api/requesters/[id]
export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { id } = await params;
        const body = await request.json();
        const { name, type, contactName, email, phone, fax, address, deliveryPreference, notes, active } = body;

        const existing = await db.select().from(requesters).where(eq(requesters.id, id)).limit(1);
        if (!existing.length) return NextResponse.json({ error: 'Not found' }, { status: 404 });

        const updates: Partial<typeof requesters.$inferInsert> = {};
        if (name !== undefined) updates.name = name;
        if (type !== undefined) updates.type = type;
        if (contactName !== undefined) updates.contactName = contactName;
        if (email !== undefined) updates.email = email;
        if (phone !== undefined) updates.phone = phone;
        if (fax !== undefined) updates.fax = fax;
        if (address !== undefined) updates.address = address;
        if (deliveryPreference !== undefined) updates.deliveryPreference = deliveryPreference;
        if (notes !== undefined) updates.notes = notes;
        if (active !== undefined) updates.active = active;

        await db.update(requesters).set(updates).where(eq(requesters.id, id));
        const updated = await db.select().from(requesters).where(eq(requesters.id, id)).limit(1);
        return NextResponse.json(updated[0]);
    } catch (error) {
        console.error('PUT /api/requesters/[id] error:', error);
        return NextResponse.json({ error: 'Failed to update requester' }, { status: 500 });
    }
}

// DELETE /api/requesters/[id] — soft delete
export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { id } = await params;
        const existing = await db.select().from(requesters).where(eq(requesters.id, id)).limit(1);
        if (!existing.length) return NextResponse.json({ error: 'Not found' }, { status: 404 });

        await db.update(requesters).set({ active: false }).where(eq(requesters.id, id));
        return NextResponse.json({ success: true, message: 'Requester deactivated' });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to deactivate requester' }, { status: 500 });
    }
}
