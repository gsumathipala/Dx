import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { cookies } from 'next/headers';
import { db } from '@/db';
import { sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';

// Helper to get authenticated user from token
async function getAuthenticatedUser() {
    const cookieStore = await cookies();
    const token = cookieStore.get('auth_token')?.value;

    if (!token) return null;

    const sessionResult = await db.select()
        .from(sessions)
        .where(eq(sessions.token, token))
        .limit(1);

    const session = sessionResult[0];
    if (!session || session.expiresAt < Date.now()) return null;

    const userResult = await db.select()
        .from(users)
        .where(eq(users.id, session.userId))
        .limit(1);

    return userResult[0] || null;
}

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const patientId = searchParams.get('patientId');

    const dbData = await readDb();
    let orderList = dbData.orders || [];

    if (patientId) {
        orderList = orderList.filter((o: any) => o.patientId === patientId);
    }

    // Build patient lookup map for name enrichment
    const patientsData: any[] = dbData.patients || [];
    const patientMap = new Map(patientsData.map((p: any) => [p.id, p]));

    // Enrich each order with patient display fields
    const enriched = orderList.map((o: any) => {
        const patient = patientMap.get(o.patientId);
        return {
            ...o,
            patientName: patient ? `${patient.lastName}, ${patient.firstName}` : null,
            patientMrn: patient?.mrn || null,
            patientDob: patient?.dob || null,
            patientGender: patient?.gender || null,
        };
    });

    // Sort by timestamp desc
    enriched.sort((a: any, b: any) => {
        const aTime = a.timestamp || a.createdAt || '';
        const bTime = b.timestamp || b.createdAt || '';
        return new Date(bTime).getTime() - new Date(aTime).getTime();
    });

    return NextResponse.json(enriched);
}

// Direct Drizzle imports to avoid legacy JSON wrapper for writes
import { orders, specimens, auditLogs, patients } from '@/db/schema';
import { generateNextAccessionNumber } from '@/lib/accession';
import { v4 as uuidv4 } from 'uuid';

export async function POST(request: Request) {
    const currentUser = await getAuthenticatedUser();
    const user = currentUser?.username || 'System';

    try {
        const body = await request.json();

        // 1. Generate Server-Side Accession Number
        const accessionNumber = generateNextAccessionNumber();

        // 2. Prepare Order Object
        const newOrderId = uuidv4();
        const newOrder = {
            id: newOrderId,
            accessionNumber: accessionNumber,
            patientId: body.patientId,
            testIds: JSON.stringify(body.testIds || []), // Store as JSON string
            priority: body.priority || 'Routine',
            status: 'Pending',
            timestamp: new Date().toISOString(),
            completedAt: null,
            // collectionDate is not in the schema explicitly but might be useful? 
            // The schema has `timestamp` and `updatedAt`. 
            // We'll stick to schema fields.
        };

        // 3. Prepare Specimen Objects
        const newSpecimens: any[] = [];
        if (body.samples && Array.isArray(body.samples)) {
            for (const sample of body.samples) {
                newSpecimens.push({
                    id: uuidv4(),
                    orderId: newOrderId,
                    type: sample.type,
                    containerId: sample.containerId || `${accessionNumber}-${sample.type.substring(0, 3)}`,
                    location: sample.location || 'Reception',
                    collectionDate: new Date().toISOString(),
                    status: sample.condition === 'Good' ? 'Received' : 'Rejected'
                });
            }
        }

        // 4. Transactional Insert (Sequence matters)
        // Note: SQLite doesn't support distinct `db.transaction()` block in better-sqlite3 wrapper easily with async/await in some versions, 
        // but we can just await them sequentially. Failures might leave partial data but much better than JSON overwrite.

        await db.insert(orders).values(newOrder);

        if (newSpecimens.length > 0) {
            await db.insert(specimens).values(newSpecimens);
        }

        // 5. Audit Log
        await db.insert(auditLogs).values({
            id: uuidv4(),
            entityType: 'Order',
            entityId: newOrderId,
            action: 'CREATE',
            userId: user,
            timestamp: new Date().toISOString(),
            details: JSON.stringify({ accessionNumber, specimenCount: newSpecimens.length })
        });

        // Return the full object including the generated accession number
        return NextResponse.json({ ...newOrder, accessionNumber }, { status: 201 });

    } catch (error) {
        console.error('Create order error:', error);
        return NextResponse.json({ error: 'Failed to create order', details: String(error) }, { status: 500 });
    }
}

