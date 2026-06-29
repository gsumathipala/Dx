import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';
import { db as drizzleDb } from '@/db';
import { specimens } from '@/db/schema';
import { eq } from 'drizzle-orm';

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const { specimenId, locationId } = body;

        if (!specimenId || !locationId) {
            return NextResponse.json({ error: 'Missing specimenId or locationId' }, { status: 400 });
        }

        const db = await readDb();

        // 1. Find Specimen (in orders?) or we assume 'specimens' collection exists?
        // Structure.md says `specimens: Specimen[]`.
        // Let's assume it exists. If not, we might need to look in orders.
        // For V1.0, let's assume `specimens` collection IS the source of truth for physical inventory.

        const specimen = db.specimens?.find((s: any) => s.id === specimenId);

        // Fallback: Check orders if specimen not standalone
        if (!specimen) {
            // If we don't have standalone specimens, we might be tracking "Order ID" as sample?
            // But usually LIS separates them.
            // If db.specimens is empty, we might need to create it from orders? 
            // For now, let's assume we are working with `db.specimens`.
            // If it fails, I'll need to fix the DB or tracking.

            // Check if we need to auto-create specimen from order?
            // Not for this task. Error if not found.
            return NextResponse.json({ error: 'Specimen not found' }, { status: 404 });
        }

        // 2. Find Location
        const locIndex = db.storageLocations?.findIndex((l: any) => l.id === locationId);
        if (locIndex === -1 || locIndex === undefined) {
            return NextResponse.json({ error: 'Location not found' }, { status: 404 });
        }
        const location = db.storageLocations[locIndex];

        // 3. Handle Old Location (Decrement)
        if (specimen.location && specimen.location !== locationId) {
            const oldLocIndex = db.storageLocations.findIndex((l: any) => l.id === specimen.location);
            if (oldLocIndex !== -1) {
                db.storageLocations[oldLocIndex].currentCount = Math.max(0, (db.storageLocations[oldLocIndex].currentCount || 0) - 1);
            }
        }

        // 4. Update Specimen via Drizzle (writeDb has no specimens handler)
        await drizzleDb.update(specimens).set({ location: locationId }).where(eq(specimens.id, specimenId));
        specimen.location = locationId;

        // 5. Update New Location
        // Check capacity
        if (location.capacity && (location.currentCount || 0) >= location.capacity) {
            return NextResponse.json({ error: 'Location is full' }, { status: 400 });
        }
        location.currentCount = (location.currentCount || 0) + 1;

        // Save updated storageLocations (virtual setting) via writeDb
        await writeDb(db);

        return NextResponse.json({ success: true, specimen });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to assign sample' }, { status: 500 });
    }
}
