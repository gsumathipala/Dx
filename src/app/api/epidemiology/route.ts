import { NextResponse } from 'next/server';
import { db } from '@/db';
import { epidemiologyNotifications, notifiableConditions, patients, orders } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

export async function GET(request: Request) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const { searchParams } = new URL(request.url);
        const statusFilter = searchParams.get('status');

        let notifications = await db.select().from(epidemiologyNotifications).orderBy(epidemiologyNotifications.detectedAt);

        if (statusFilter) {
            notifications = notifications.filter((n) => n.status === statusFilter);
        }

        // Join conditions, patients, orders
        const conditionIds = [...new Set(notifications.map((n) => n.conditionId))];
        const patientIds = [...new Set(notifications.map((n) => n.patientId))];
        const orderIds = [...new Set(notifications.map((n) => n.orderId))];

        const allConditions = conditionIds.length > 0
            ? await db.select().from(notifiableConditions)
            : [];
        const allPatients = patientIds.length > 0
            ? await db.select().from(patients)
            : [];
        const allOrders = orderIds.length > 0
            ? await db.select().from(orders)
            : [];

        const conditionMap = new Map(allConditions.map((c) => [c.id, c]));
        const patientMap = new Map(allPatients.map((p) => [p.id, p]));
        const orderMap = new Map(allOrders.map((o) => [o.id, o]));

        const enriched = notifications.map((n) => {
            const condition = conditionMap.get(n.conditionId);
            const patient = patientMap.get(n.patientId);
            const order = orderMap.get(n.orderId);
            return {
                ...n,
                condition: condition ?? null,
                patient: patient
                    ? {
                          id: patient.id,
                          name: `${patient.firstName} ${patient.lastName}`,
                          mrn: patient.mrn,
                          dob: patient.dob,
                          gender: patient.gender,
                      }
                    : null,
                order: order
                    ? {
                          id: order.id,
                          accessionNumber: order.accessionNumber,
                          timestamp: order.timestamp,
                          status: order.status,
                      }
                    : null,
            };
        });

        return NextResponse.json(enriched);
    } catch (error) {
        console.error('Epidemiology GET error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

export async function POST(request: Request) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        const currentUser = JSON.parse(session.value);

        if (!['manager', 'admin'].includes(currentUser.role)) {
            return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
        }

        const body = await request.json();
        const { orderId, patientId, conditionId } = body;

        if (!orderId || !patientId || !conditionId) {
            return NextResponse.json({ error: 'orderId, patientId, and conditionId are required' }, { status: 400 });
        }

        const newNotification = {
            id: uuidv4(),
            orderId,
            patientId,
            conditionId,
            detectedAt: new Date().toISOString(),
            status: 'Pending',
            reviewedBy: null,
            reviewedAt: null,
            submittedBy: null,
            submittedAt: null,
            notes: null,
        };

        await db.insert(epidemiologyNotifications).values(newNotification);

        return NextResponse.json(newNotification, { status: 201 });
    } catch (error) {
        console.error('Epidemiology POST error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
