import { NextResponse } from 'next/server';
import { db } from '@/db';
import { calculatedTests } from '@/db/schema';
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

// GET /api/calculated-tests — list all calculated test definitions
export async function GET() {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const rows = await db.select().from(calculatedTests);
        return NextResponse.json(rows);
    } catch (error) {
        console.error('GET /api/calculated-tests error:', error);
        return NextResponse.json({ error: 'Failed to fetch calculated tests' }, { status: 500 });
    }
}

// POST /api/calculated-tests — create a calculated test (admin only)
export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (currentUser.role !== 'admin') {
        return NextResponse.json({ error: 'Forbidden — admin only' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { testCode, name, formula, unit } = body;

        if (!testCode || !name || !formula) {
            return NextResponse.json({ error: 'testCode, name, and formula are required' }, { status: 400 });
        }

        const newTest = {
            id: uuidv4(),
            testCode,
            name,
            formula: typeof formula === 'string' ? formula : JSON.stringify(formula),
            unit: unit || null,
            active: true,
            createdAt: new Date().toISOString(),
        };

        await db.insert(calculatedTests).values(newTest);
        return NextResponse.json(newTest, { status: 201 });
    } catch (error: any) {
        if (error?.message?.includes('UNIQUE')) {
            return NextResponse.json({ error: 'Test code already exists' }, { status: 409 });
        }
        console.error('POST /api/calculated-tests error:', error);
        return NextResponse.json({ error: 'Failed to create calculated test' }, { status: 500 });
    }
}
