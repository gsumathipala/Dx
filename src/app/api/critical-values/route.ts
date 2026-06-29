import { NextResponse } from 'next/server';
import { db } from '@/db';
import { criticalValueNotifications, orders, patients } from '@/db/schema';
import { eq, and } from 'drizzle-orm';
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

// GET /api/critical-values — returns all notifications
// Query params: ?status=Pending to filter by status
export async function GET(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const { searchParams } = new URL(request.url);
        const statusFilter = searchParams.get('status');

        let notifications;
        if (statusFilter) {
            notifications = await db.select().from(criticalValueNotifications).where(
                eq(criticalValueNotifications.status, statusFilter)
            );
        } else {
            notifications = await db.select().from(criticalValueNotifications);
        }

        // Sort by createdAt descending (newest first)
        notifications.sort((a, b) => (b.createdAt > a.createdAt ? 1 : -1));

        // Enrich with patient name, MRN, and accession number
        const enriched = await Promise.all(notifications.map(async (notif) => {
            let patientName = '';
            let mrn = '';
            let accessionNumber = '';

            try {
                const orderRows = await db.select().from(orders).where(eq(orders.id, notif.orderId)).limit(1);
                if (orderRows.length > 0) {
                    accessionNumber = orderRows[0].accessionNumber;
                    const patientRows = await db.select().from(patients).where(eq(patients.id, orderRows[0].patientId)).limit(1);
                    if (patientRows.length > 0) {
                        patientName = `${patientRows[0].firstName} ${patientRows[0].lastName}`;
                        mrn = patientRows[0].mrn;
                    }
                }
            } catch { /* non-fatal */ }

            return {
                ...notif,
                patientName,
                mrn,
                accessionNumber,
            };
        }));

        return NextResponse.json(enriched);
    } catch (error) {
        console.error('GET critical-values error:', error);
        return NextResponse.json({ error: 'Failed to fetch critical value notifications' }, { status: 500 });
    }
}

// POST /api/critical-values — create a new notification
export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const body = await request.json();
        const { orderId, patientId, testId, testCode, value, threshold, criticalType } = body;

        if (!orderId || !patientId || !testId || !testCode || !value || !threshold || !criticalType) {
            return NextResponse.json({
                error: 'Missing required fields: orderId, patientId, testId, testCode, value, threshold, criticalType'
            }, { status: 400 });
        }

        if (!['HIGH', 'LOW'].includes(criticalType)) {
            return NextResponse.json({ error: 'criticalType must be "HIGH" or "LOW"' }, { status: 400 });
        }

        const newNotification = {
            id: uuidv4(),
            orderId,
            patientId,
            testId,
            testCode,
            value: String(value),
            threshold: String(threshold),
            criticalType,
            status: 'Pending',
            createdAt: new Date().toISOString(),
            createdBy: currentUser.username,
        };

        await db.insert(criticalValueNotifications).values(newNotification);
        return NextResponse.json(newNotification, { status: 201 });
    } catch (error) {
        console.error('POST critical-values error:', error);
        return NextResponse.json({ error: 'Failed to create critical value notification' }, { status: 500 });
    }
}
