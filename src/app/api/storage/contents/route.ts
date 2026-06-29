import { NextResponse } from 'next/server';
import { readDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const locationId = searchParams.get('locationId');

        if (!locationId) {
            return NextResponse.json({ error: 'locationId required' }, { status: 400 });
        }

        const db = await readDb();
        // Return all specimens in this location
        const specimens = db.specimens?.filter((s: any) => s.storageLocationId === locationId) || [];

        return NextResponse.json(specimens);
    } catch (error) {
        return NextResponse.json({ error: 'Failed to fetch contents' }, { status: 500 });
    }
}
