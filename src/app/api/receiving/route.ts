import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import { db } from '@/db';
import { specimenReceiving, specimens, orders, patients, sessions, users } from '@/db/schema';
import { eq, and, gte } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

async function getAuthenticatedUser() {
    const cookieStore = await cookies();
    const token = cookieStore.get('auth_token')?.value;
    if (!token) return null;
    const sessionResult = await db.select().from(sessions).where(eq(sessions.token, token)).limit(1);
    const session = sessionResult[0];
    if (!session || session.expiresAt < Date.now()) return null;
    const userResult = await db.select().from(users).where(eq(users.id, session.userId)).limit(1);
    return userResult[0] || null;
}

export async function GET(request: Request) {
    try {
        const { searchParams } = new URL(request.url);
        const statusFilter = searchParams.get('status');

        // Get all receiving records joined with specimens, orders, patients
        const allReceiving = await db.select().from(specimenReceiving);
        const allSpecimens = await db.select().from(specimens);
        const allOrders = await db.select().from(orders);
        const allPatients = await db.select().from(patients);

        const specimenMap = new Map(allSpecimens.map(s => [s.id, s]));
        const orderMap = new Map(allOrders.map(o => [o.id, o]));
        const patientMap = new Map(allPatients.map(p => [p.id, p]));

        let records = allReceiving.map(r => {
            const specimen = specimenMap.get(r.specimenId);
            const order = orderMap.get(r.orderId);
            const patient = order ? patientMap.get(order.patientId) : null;
            return {
                ...r,
                specimenType: specimen?.type || '',
                accessionNumber: order?.accessionNumber || '',
                patientName: patient ? `${patient.firstName} ${patient.lastName}` : '',
                patientMrn: patient?.mrn || '',
            };
        });

        if (statusFilter) {
            records = records.filter(r => r.status === statusFilter);
        }

        // Sort newest first
        records.sort((a, b) => new Date(b.receivedAt).getTime() - new Date(a.receivedAt).getTime());

        return NextResponse.json(records);
    } catch (error) {
        console.error('GET /api/receiving error:', error);
        return NextResponse.json({ error: 'Failed to fetch receiving records', details: String(error) }, { status: 500 });
    }
}

export async function POST(request: Request) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { specimenId, orderId, condition, conditionNotes, rejectionReason, temperature, volume } = body;

        if (!specimenId || !orderId || !condition) {
            return NextResponse.json({ error: 'specimenId, orderId, and condition are required' }, { status: 400 });
        }

        // Determine status from condition
        let status: 'Accepted' | 'Rejected' | 'Recollection-Required';
        if (condition === 'Rejected') {
            status = 'Rejected';
        } else if (condition === 'Marginal') {
            status = 'Recollection-Required';
        } else {
            status = 'Accepted';
        }

        const now = new Date().toISOString();
        const id = uuidv4();

        // Insert receiving record
        await db.insert(specimenReceiving).values({
            id,
            specimenId,
            orderId,
            receivedAt: now,
            receivedBy: currentUser.username,
            condition,
            conditionNotes: conditionNotes || null,
            rejectionReason: rejectionReason || null,
            temperature: temperature || null,
            volume: volume ? Number(volume) : null,
            status,
        });

        // Update specimen status
        const specimenStatus = condition === 'Rejected' ? 'Rejected' : 'Received';
        await db.update(specimens)
            .set({ status: specimenStatus })
            .where(eq(specimens.id, specimenId));

        return NextResponse.json({ id, status }, { status: 201 });
    } catch (error) {
        console.error('POST /api/receiving error:', error);
        return NextResponse.json({ error: 'Failed to create receiving record', details: String(error) }, { status: 500 });
    }
}
