import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import type { CoCEvent, CoCEventCreate, CoCTimeline } from '@/types/coc-event';
import { createHash } from 'crypto';
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
 * GET /api/coc?sampleId={id}
 * Retrieve complete Chain of Custody timeline for a sample
 */
export async function GET(request: Request) {
    const authUser = await getAuthenticatedUser();
    if (!authUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const sampleId = searchParams.get('sampleId');
        const accessionNumber = searchParams.get('accessionNumber');

        if (!sampleId && !accessionNumber) {
            return NextResponse.json(
                { error: 'sampleId or accessionNumber required' },
                { status: 400 }
            );
        }

        const dbData = await readDb();
        const cocEvents: CoCEvent[] = dbData.cocEvents || [];

        // Filter events by sampleId or accessionNumber
        let filteredEvents = cocEvents;
        if (sampleId) {
            filteredEvents = cocEvents.filter(e => e.sampleId === sampleId);
        } else if (accessionNumber) {
            filteredEvents = cocEvents.filter(e => e.accessionNumber === accessionNumber);
        }

        // Sort by timestamp (oldest first)
        filteredEvents.sort((a, b) =>
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

        // Determine current location and status
        const lastEvent = filteredEvents[filteredEvents.length - 1];
        const currentLocation = lastEvent?.toLocation || lastEvent?.location;
        const currentStatus = lastEvent?.eventType || 'UNKNOWN';

        const timeline: CoCTimeline = {
            sampleId: sampleId || filteredEvents[0]?.sampleId || '',
            accessionNumber: accessionNumber || filteredEvents[0]?.accessionNumber || '',
            events: filteredEvents,
            currentLocation,
            currentStatus
        };

        return NextResponse.json(timeline);
    } catch (error) {
        console.error('CoC GET error:', error);
        return NextResponse.json(
            { error: 'Failed to retrieve CoC timeline' },
            { status: 500 }
        );
    }
}

/**
 * POST /api/coc
 * Log a new Chain of Custody event (REQUIRES AUTHENTICATION)
 */
export async function POST(request: Request) {
    // SECURITY: Require authentication for Chain of Custody logging
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) {
        return NextResponse.json({ error: 'Unauthorized - Authentication required for CoC events' }, { status: 401 });
    }

    try {
        const body: CoCEventCreate = await request.json();

        // Validation
        if (!body.sampleId || !body.accessionNumber || !body.eventType) {
            return NextResponse.json(
                { error: 'Missing required fields: sampleId, accessionNumber, eventType' },
                { status: 400 }
            );
        }

        const dbData = await readDb();
        if (!dbData.cocEvents) dbData.cocEvents = [];

        // Generate digital signature (hash of event data for tamper detection)
        const signatureData = JSON.stringify({
            sampleId: body.sampleId,
            eventType: body.eventType,
            performedBy: currentUser.username, // Use authenticated user
            timestamp: new Date().toISOString()
        });
        const signature = createHash('sha256').update(signatureData).digest('hex');

        // Create new CoC event
        const newEvent: CoCEvent = {
            id: Date.now().toString(),
            sampleId: body.sampleId,
            accessionNumber: body.accessionNumber,
            eventType: body.eventType,
            timestamp: new Date().toISOString(),
            performedBy: currentUser.username, // Use authenticated user
            performedByName: currentUser.name || currentUser.username,
            location: body.location,
            fromLocation: body.fromLocation,
            toLocation: body.toLocation,
            notes: body.notes,
            signature,
            metadata: body.metadata
        };

        dbData.cocEvents.push(newEvent);
        await writeDb(dbData);

        return NextResponse.json(newEvent, { status: 201 });
    } catch (error) {
        console.error('CoC POST error:', error);
        return NextResponse.json(
            { error: 'Failed to create CoC event' },
            { status: 500 }
        );
    }
}

/**
 * DELETE /api/coc/{id}
 * DISABLED for security - CoC events should be immutable for legal compliance.
 * This endpoint is commented out.
 */
// export async function DELETE(request: Request) {
//     return NextResponse.json({ error: 'DELETE is disabled - CoC events are immutable for legal compliance' }, { status: 403 });
// }

