import { NextResponse } from 'next/server';
import { db } from '@/db';
import { loincCodes } from '@/db/schema';
import { or, like } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

async function getCurrentUser() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return null;
    try {
        return JSON.parse(session.value);
    } catch {
        return null;
    }
}

// GET /api/loinc — search LOINC codes
// Query: ?q=glucose — searches longName or loincCode, limit 50
export async function GET(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const q = searchParams.get('q');

        let rows;
        if (q && q.trim()) {
            const pattern = `%${q.trim()}%`;
            rows = await db.select().from(loincCodes).where(
                or(
                    like(loincCodes.longName, pattern),
                    like(loincCodes.loincCode, pattern),
                    like(loincCodes.component, pattern)
                )
            ).limit(50);
        } else {
            rows = await db.select().from(loincCodes).limit(50);
        }

        return NextResponse.json(rows);
    } catch (error) {
        console.error('GET /api/loinc error:', error);
        return NextResponse.json({ error: 'Failed to fetch LOINC codes' }, { status: 500 });
    }
}

// POST /api/loinc — create/import a LOINC code (admin only)
export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (currentUser.role !== 'admin') {
        return NextResponse.json({ error: 'Forbidden — admin only' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { loincCode, longName, shortName, component, property, timeAspect, system, scale, method } = body;

        if (!loincCode || !longName) {
            return NextResponse.json({ error: 'loincCode and longName are required' }, { status: 400 });
        }

        const newCode = {
            id: uuidv4(),
            loincCode,
            longName,
            shortName: shortName || null,
            component: component || null,
            property: property || null,
            timeAspect: timeAspect || null,
            system: system || null,
            scale: scale || null,
            method: method || null,
            status: 'Active',
        };

        await db.insert(loincCodes).values(newCode);
        return NextResponse.json(newCode, { status: 201 });
    } catch (error: any) {
        if (error?.message?.includes('UNIQUE')) {
            return NextResponse.json({ error: 'LOINC code already exists' }, { status: 409 });
        }
        console.error('POST /api/loinc error:', error);
        return NextResponse.json({ error: 'Failed to create LOINC code' }, { status: 500 });
    }
}
