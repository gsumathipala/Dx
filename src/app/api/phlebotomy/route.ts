import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import { db } from '@/db';
import { phlebotomySchedules, patients, sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';
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
        const dateFilter = searchParams.get('date'); // YYYY-MM-DD

        const allSchedules = await db.select().from(phlebotomySchedules);
        const allPatients = await db.select().from(patients);
        const patientMap = new Map(allPatients.map(p => [p.id, p]));

        let records = allSchedules.map(s => {
            const patient = patientMap.get(s.patientId);
            return {
                ...s,
                patientName: patient ? `${patient.firstName} ${patient.lastName}` : 'Unknown',
                mrn: patient?.mrn || '',
            };
        });

        if (statusFilter) {
            records = records.filter(r => r.status === statusFilter);
        }

        if (dateFilter) {
            records = records.filter(r => r.scheduledAt?.startsWith(dateFilter));
        }

        // Sort by scheduledAt ascending
        records.sort((a, b) => new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime());

        return NextResponse.json(records);
    } catch (error) {
        console.error('GET /api/phlebotomy error:', error);
        return NextResponse.json({ error: 'Failed to fetch phlebotomy schedules', details: String(error) }, { status: 500 });
    }
}

export async function POST(request: Request) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { patientId, orderId, wardLocation, scheduledAt, collectionType, testIds, notes, assignedTo } = body;

        if (!patientId || !wardLocation || !scheduledAt || !collectionType) {
            return NextResponse.json({ error: 'patientId, wardLocation, scheduledAt, and collectionType are required' }, { status: 400 });
        }

        const id = uuidv4();
        await db.insert(phlebotomySchedules).values({
            id,
            patientId,
            orderId: orderId || null,
            wardLocation,
            scheduledAt,
            collectionType,
            testIds: Array.isArray(testIds) ? JSON.stringify(testIds) : testIds || null,
            assignedTo: assignedTo || null,
            status: 'Scheduled',
            notes: notes || null,
            completedAt: null,
            createdAt: new Date().toISOString(),
        });

        return NextResponse.json({ id }, { status: 201 });
    } catch (error) {
        console.error('POST /api/phlebotomy error:', error);
        return NextResponse.json({ error: 'Failed to create phlebotomy schedule', details: String(error) }, { status: 500 });
    }
}
