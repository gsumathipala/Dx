import { NextResponse } from 'next/server';
import { db } from '@/db';
import { epidemiologyNotifications } from '@/db/schema';
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
        const { status, notes } = body;

        const now = new Date().toISOString();
        const updateData: Record<string, unknown> = {};

        if (status) updateData.status = status;
        if (notes !== undefined) updateData.notes = notes;

        if (status === 'Reviewed') {
            updateData.reviewedBy = currentUser.username;
            updateData.reviewedAt = now;
        } else if (status === 'Submitted') {
            updateData.submittedBy = currentUser.username;
            updateData.submittedAt = now;
        }

        await db.update(epidemiologyNotifications).set(updateData).where(eq(epidemiologyNotifications.id, id));

        const [updated] = await db
            .select()
            .from(epidemiologyNotifications)
            .where(eq(epidemiologyNotifications.id, id))
            .limit(1);

        return NextResponse.json(updated);
    } catch (error) {
        console.error('Epidemiology PUT error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
