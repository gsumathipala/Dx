import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import type { Aliquot, AliquotCreate, SampleWithAliquots } from '@/types/aliquot';
import { generateAliquotIdentifier, generateAliquotNumber } from '@/types/aliquot';
import { getAuthUser } from '@/lib/auth';

/**
 * GET /api/samples/aliquot?parentSampleId={id}
 * Retrieve all aliquots for a parent sample
 */
export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const parentSampleId = searchParams.get('parentSampleId');
        const accessionNumber = searchParams.get('accessionNumber');

        if (!parentSampleId && !accessionNumber) {
            return NextResponse.json(
                { error: 'parentSampleId or accessionNumber required' },
                { status: 400 }
            );
        }

        const db = await readDb();
        const aliquots: Aliquot[] = db.aliquots || [];

        // Filter aliquots
        let filteredAliquots = aliquots;
        if (parentSampleId) {
            filteredAliquots = aliquots.filter(a => a.parentSampleId === parentSampleId);
        } else if (accessionNumber) {
            filteredAliquots = aliquots.filter(a => a.parentAccessionNumber === accessionNumber);
        }

        // Sort by creation date
        filteredAliquots.sort((a, b) =>
            new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
        );

        return NextResponse.json(filteredAliquots);
    } catch (error) {
        console.error('Aliquot GET error:', error);
        return NextResponse.json(
            { error: 'Failed to retrieve aliquots' },
            { status: 500 }
        );
    }
}

/**
 * POST /api/samples/aliquot
 * Create new aliquot(s) from parent sample
 */
export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body: AliquotCreate = await request.json();

        // Validation
        if (!body.parentSampleId || !body.parentAccessionNumber || !body.type || !body.createdBy) {
            return NextResponse.json(
                { error: 'Missing required fields: parentSampleId, parentAccessionNumber, type, createdBy' },
                { status: 400 }
            );
        }

        const db = await readDb();
        if (!db.aliquots) db.aliquots = [];

        const count = body.count || 1;
        const createdAliquots: Aliquot[] = [];

        // Get existing aliquot count for this parent to continue numbering
        const existingAliquots = db.aliquots.filter(
            (a: Aliquot) => a.parentSampleId === body.parentSampleId
        );
        const startIndex = existingAliquots.length;

        // Create aliquots
        for (let i = 0; i < count; i++) {
            const aliquotNumber = generateAliquotNumber(startIndex + i);
            const fullIdentifier = generateAliquotIdentifier(body.parentAccessionNumber, aliquotNumber);

            const newAliquot: Aliquot = {
                id: `${Date.now()}-${i}`,
                parentSampleId: body.parentSampleId,
                parentAccessionNumber: body.parentAccessionNumber,
                aliquotNumber,
                fullIdentifier,
                type: body.type,
                volume: body.volume,
                volumeUnit: body.volumeUnit || 'mL',
                containerId: body.containerId,
                location: body.location,
                createdAt: new Date().toISOString(),
                createdBy: body.createdBy,
                createdByName: body.createdByName,
                purpose: body.purpose,
                status: 'Active'
            };

            db.aliquots.push(newAliquot);
            createdAliquots.push(newAliquot);

            // Log Chain of Custody event for aliquot creation
            if (!db.cocEvents) db.cocEvents = [];
            db.cocEvents.push({
                id: `${Date.now()}-coc-${i}`,
                sampleId: fullIdentifier,
                accessionNumber: body.parentAccessionNumber,
                eventType: 'ALIQUOTED',
                timestamp: new Date().toISOString(),
                performedBy: body.createdBy,
                performedByName: body.createdByName,
                location: body.location,
                notes: `Aliquot ${aliquotNumber} created from parent sample. ${body.purpose ? `Purpose: ${body.purpose}` : ''}`,
                signature: '', // Would generate proper signature in production
                metadata: {
                    parentSampleId: body.parentSampleId,
                    aliquotNumber,
                    volume: body.volume,
                    volumeUnit: body.volumeUnit
                }
            });
        }

        await writeDb(db);

        return NextResponse.json(
            count === 1 ? createdAliquots[0] : createdAliquots,
            { status: 201 }
        );
    } catch (error) {
        console.error('Aliquot POST error:', error);
        return NextResponse.json(
            { error: 'Failed to create aliquot(s)' },
            { status: 500 }
        );
    }
}

/**
 * PUT /api/samples/aliquot/{id}
 * Update aliquot status (e.g., mark as used or disposed)
 */
export async function PUT(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const { id, status, performedBy, performedByName } = body;

        if (!id || !status) {
            return NextResponse.json(
                { error: 'Missing required fields: id, status' },
                { status: 400 }
            );
        }

        const db = await readDb();
        if (!db.aliquots) db.aliquots = [];

        const aliquot = db.aliquots.find((a: Aliquot) => a.id === id);
        if (!aliquot) {
            return NextResponse.json({ error: 'Aliquot not found' }, { status: 404 });
        }

        // Update status
        aliquot.status = status;
        if (status === 'Used') {
            aliquot.usedAt = new Date().toISOString();
        } else if (status === 'Disposed') {
            aliquot.disposedAt = new Date().toISOString();
        }

        // Log CoC event
        if (!db.cocEvents) db.cocEvents = [];
        db.cocEvents.push({
            id: `${Date.now()}-coc`,
            sampleId: aliquot.fullIdentifier,
            accessionNumber: aliquot.parentAccessionNumber,
            eventType: status === 'Disposed' ? 'DISPOSED' : 'TESTED',
            timestamp: new Date().toISOString(),
            performedBy: performedBy || 'system',
            performedByName: performedByName || 'System',
            location: aliquot.location,
            notes: `Aliquot marked as ${status}`,
            signature: '',
            metadata: { previousStatus: aliquot.status, newStatus: status }
        });

        await writeDb(db);

        return NextResponse.json(aliquot);
    } catch (error) {
        console.error('Aliquot PUT error:', error);
        return NextResponse.json(
            { error: 'Failed to update aliquot' },
            { status: 500 }
        );
    }
}
