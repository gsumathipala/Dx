import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit, generateZPLLabel } from '@/lib/db';
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

/**
 * Specimens API - APHL 2019 Compliant Specimen-Centric Model
 */

// GET: List specimens
export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const orderId = searchParams.get('orderId');
    const patientId = searchParams.get('patientId');
    const accession = searchParams.get('accession');

    const dbData = await readDb();
    let specimens = dbData.specimens || [];

    if (orderId) {
        specimens = specimens.filter((s: any) => s.orderId === orderId);
    }
    if (patientId) {
        specimens = specimens.filter((s: any) => s.patientId === patientId);
    }
    if (accession) {
        specimens = specimens.filter((s: any) =>
            s.accessionNumber?.toLowerCase().includes(accession.toLowerCase())
        );
    }

    return NextResponse.json(specimens);
}

// POST: Create/Register new specimen
export async function POST(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    // Allow clerk, scientist, manager, admin to register specimens
    if (!['admin', 'manager', 'scientist', 'clerk'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const {
            orderId,
            patientId,
            type,
            containerId,
            collectionDate,
            storageLocation,
            testIds
        } = body;

        const dbData = await readDb();

        // Generate unique accession number if not provided
        const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        const count = (dbData.specimens || []).filter((s: any) =>
            s.accessionNumber?.startsWith(`ACC-${dateStr}`)
        ).length + 1;
        const accessionNumber = `ACC-${dateStr}-${count.toString().padStart(4, '0')}`;

        const newSpecimen = {
            id: `spec-${Date.now()}`,
            accessionNumber,
            orderId,
            patientId,
            type: type || 'Whole Blood',
            containerId: containerId || `CNT-${Date.now()}`,
            collectionDate: collectionDate || new Date().toISOString(),
            receivedDate: new Date().toISOString(),
            receivedBy: currentUser.username,
            storageLocation: storageLocation || 'Pending Assignment',
            status: 'Received',
            rejectionReason: null,
            testIds: testIds || [],
            chainOfCustody: [
                {
                    timestamp: new Date().toISOString(),
                    action: 'RECEIVED',
                    location: storageLocation || 'Reception',
                    performedBy: currentUser.username,
                    notes: 'Specimen logged into system'
                }
            ]
        };

        if (!dbData.specimens) dbData.specimens = [];
        dbData.specimens.push(newSpecimen);

        // Audit Log
        await logAudit(dbData, 'Specimen', newSpecimen.id, 'CREATE', null, newSpecimen, currentUser.username);

        await writeDb(dbData);

        return NextResponse.json(newSpecimen, { status: 201 });

    } catch (error) {
        console.error('Specimen creation error:', error);
        return NextResponse.json({ error: 'Failed to create specimen' }, { status: 500 });
    }
}

// PUT: Update specimen (status, location, etc.)
export async function PUT(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const body = await request.json();
        const { id, action, ...updates } = body;

        const dbData = await readDb();
        const index = (dbData.specimens || []).findIndex((s: any) => s.id === id);

        if (index === -1) {
            return NextResponse.json({ error: 'Specimen not found' }, { status: 404 });
        }

        const oldValue = { ...dbData.specimens[index] };

        // Handle specific actions
        if (action === 'REJECT') {
            dbData.specimens[index].status = 'Rejected';
            dbData.specimens[index].rejectionReason = updates.rejectionReason || 'Not specified';
            dbData.specimens[index].rejectedBy = currentUser.username;
            dbData.specimens[index].rejectedAt = new Date().toISOString();
        } else if (action === 'START_TESTING') {
            dbData.specimens[index].status = 'In Testing';
            dbData.specimens[index].testingStartedAt = new Date().toISOString();
            dbData.specimens[index].testingStartedBy = currentUser.username;
        } else if (action === 'COMPLETE') {
            dbData.specimens[index].status = 'Completed';
            dbData.specimens[index].completedAt = new Date().toISOString();
        } else if (action === 'TRANSFER') {
            // Chain of custody transfer
            if (!dbData.specimens[index].chainOfCustody) dbData.specimens[index].chainOfCustody = [];
            dbData.specimens[index].chainOfCustody.push({
                timestamp: new Date().toISOString(),
                action: 'TRANSFERRED',
                fromLocation: dbData.specimens[index].storageLocation,
                toLocation: updates.storageLocation,
                performedBy: currentUser.username,
                notes: updates.notes || ''
            });
            dbData.specimens[index].storageLocation = updates.storageLocation;
        } else {
            // General update
            Object.assign(dbData.specimens[index], updates);
        }

        dbData.specimens[index].updatedAt = new Date().toISOString();
        dbData.specimens[index].updatedBy = currentUser.username;

        // Audit Log
        await logAudit(dbData, 'Specimen', id, action || 'UPDATE', oldValue, dbData.specimens[index], currentUser.username);

        await writeDb(dbData);

        return NextResponse.json(dbData.specimens[index]);

    } catch (error) {
        return NextResponse.json({ error: 'Failed to update specimen' }, { status: 500 });
    }
}
