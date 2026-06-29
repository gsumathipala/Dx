import { NextResponse } from 'next/server';
import { db } from '@/db';
import { distributionRules } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        const currentUser = JSON.parse(session.value);

        if (!['manager', 'admin'].includes(currentUser.role)) {
            return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
        }

        const { id } = await params;
        const body = await request.json();
        const { requesterId, testId, method, destination, autoRelease, active } = body;

        const updateData: Record<string, unknown> = {};
        if (requesterId !== undefined) updateData.requesterId = requesterId;
        if (testId !== undefined) updateData.testId = testId;
        if (method !== undefined) updateData.method = method;
        if (destination !== undefined) updateData.destination = destination;
        if (autoRelease !== undefined) updateData.autoRelease = autoRelease;
        if (active !== undefined) updateData.active = active;

        await db.update(distributionRules).set(updateData).where(eq(distributionRules.id, id));

        const [updated] = await db.select().from(distributionRules).where(eq(distributionRules.id, id)).limit(1);

        return NextResponse.json(updated);
    } catch (error) {
        console.error('Distribution rule PUT error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        const currentUser = JSON.parse(session.value);

        if (!['manager', 'admin'].includes(currentUser.role)) {
            return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
        }

        const { id } = await params;
        await db.delete(distributionRules).where(eq(distributionRules.id, id));

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Distribution rule DELETE error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
