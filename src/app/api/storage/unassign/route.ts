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
        const { specimenId } = body;

        if (!specimenId) {
            return NextResponse.json({ error: 'Missing specimenId' }, { status: 400 });
        }

        const db = await readDb();
        const specimen = db.specimens?.find((s: any) => s.id === specimenId);

        if (!specimen) {
            return NextResponse.json({ error: 'Specimen not found' }, { status: 404 });
        }

        // The specimens schema uses `location`, not `storageLocationId`
        if (specimen.location) {
            const locIndex = db.storageLocations?.findIndex((l: any) => l.id === specimen.location);
            if (locIndex !== -1 && locIndex !== undefined) {
                db.storageLocations[locIndex].currentCount = Math.max(0, (db.storageLocations[locIndex].currentCount || 0) - 1);
            }
            // Update specimen via Drizzle (writeDb has no specimens handler)
            await drizzleDb.update(specimens).set({ location: null }).where(eq(specimens.id, specimenId));
            // Save updated storageLocations (virtual setting) via writeDb
            await writeDb(db);
        }

        return NextResponse.json({ success: true });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to unassign sample' }, { status: 500 });
    }
}
