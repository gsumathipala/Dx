import { NextResponse } from 'next/server';
import { db } from '@/db';
import { criticalValueNotifications, criticalValueAcknowledgments } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

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

// POST /api/critical-values/[id]/ack — acknowledge a critical value notification
// Body: { notifiedClinician, notificationMethod, notes }
export async function POST(
    request: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const { id } = await params;
        const body = await request.json();
        const { notifiedClinician, notificationMethod, notes, escalatedTo } = body;

        if (!notifiedClinician || !notificationMethod) {
            return NextResponse.json({
                error: 'Missing required fields: notifiedClinician, notificationMethod'
            }, { status: 400 });
        }

        if (!['phone', 'fax', 'in-person'].includes(notificationMethod)) {
            return NextResponse.json({
                error: 'notificationMethod must be "phone", "fax", or "in-person"'
            }, { status: 400 });
        }

        // Find the notification
        const notifRows = await db.select().from(criticalValueNotifications).where(
            eq(criticalValueNotifications.id, id)
        ).limit(1);

        if (notifRows.length === 0) {
            return NextResponse.json({ error: 'Notification not found' }, { status: 404 });
        }

        const notif = notifRows[0];
        if (notif.status !== 'Pending') {
            return NextResponse.json({ error: 'Notification is already acknowledged or escalated' }, { status: 409 });
        }

        const now = new Date().toISOString();

        // Create acknowledgment record
        const ackRecord = {
            id: uuidv4(),
            notificationId: id,
            acknowledgedBy: currentUser.username,
            acknowledgedAt: now,
            notifiedClinician,
            notificationMethod,
            notes: notes || null,
            escalatedTo: escalatedTo || null,
        };

        await db.insert(criticalValueAcknowledgments).values(ackRecord);

        // Update notification status
        await db.update(criticalValueNotifications).set({
            status: 'Acknowledged',
        }).where(eq(criticalValueNotifications.id, id));

        return NextResponse.json({ success: true, acknowledgment: ackRecord });
    } catch (error) {
        console.error('POST critical-value ack error:', error);
        return NextResponse.json({ error: 'Failed to acknowledge critical value notification' }, { status: 500 });
    }
}
