import { NextResponse } from 'next/server';
import { db } from '@/db';
import { demographicReferenceRanges } from '@/db/schema';
import { eq } from 'drizzle-orm';
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

// GET /api/demographic-ranges — list all, ?testCode=GLUC to filter
export async function GET(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const testCode = searchParams.get('testCode');

        let rows = await db.select().from(demographicReferenceRanges);

        if (testCode) {
            rows = rows.filter(r => r.testCode === testCode);
        }

        return NextResponse.json(rows);
    } catch (error) {
        console.error('GET /api/demographic-ranges error:', error);
        return NextResponse.json({ error: 'Failed to fetch demographic reference ranges' }, { status: 500 });
    }
}

// POST /api/demographic-ranges — create a range (manager/admin only)
export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const {
            testId, testCode, ageMin, ageMax, gender, pregnancy, trimester,
            lowNormal, highNormal, lowCritical, highCritical, unit, notes
        } = body;

        if (!testId || !testCode) {
            return NextResponse.json({ error: 'testId and testCode are required' }, { status: 400 });
        }

        const newRange = {
            id: uuidv4(),
            testId,
            testCode,
            ageMin: ageMin != null ? Number(ageMin) : null,
            ageMax: ageMax != null ? Number(ageMax) : null,
            gender: gender || 'All',
            pregnancy: pregnancy ? true : false,
            trimester: trimester != null ? Number(trimester) : null,
            lowNormal: lowNormal != null ? Number(lowNormal) : null,
            highNormal: highNormal != null ? Number(highNormal) : null,
            lowCritical: lowCritical != null ? Number(lowCritical) : null,
            highCritical: highCritical != null ? Number(highCritical) : null,
            unit: unit || null,
            notes: notes || null,
            active: true,
            createdAt: new Date().toISOString(),
        };

        await db.insert(demographicReferenceRanges).values(newRange);
        return NextResponse.json(newRange, { status: 201 });
    } catch (error) {
        console.error('POST /api/demographic-ranges error:', error);
        return NextResponse.json({ error: 'Failed to create demographic reference range' }, { status: 500 });
    }
}
