import { NextResponse } from 'next/server';
import { db } from '@/db';
import { retentionPolicies } from '@/db/schema';
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

// GET /api/retention — list all retention policies
export async function GET() {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const policies = await db.select().from(retentionPolicies);
        return NextResponse.json(policies);
    } catch (error) {
        console.error('GET /api/retention error:', error);
        return NextResponse.json({ error: 'Failed to fetch retention policies' }, { status: 500 });
    }
}

// POST /api/retention — create a retention policy (admin only)
export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (currentUser.role !== 'admin') {
        return NextResponse.json({ error: 'Forbidden — admin only' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { specimenType, retentionDays, temperature, disposalMethod, notes } = body;

        if (!specimenType || retentionDays == null) {
            return NextResponse.json({ error: 'specimenType and retentionDays are required' }, { status: 400 });
        }

        const newPolicy = {
            id: uuidv4(),
            specimenType,
            retentionDays: Number(retentionDays),
            temperature: temperature || null,
            disposalMethod: disposalMethod || 'Biohazard Disposal',
            active: true,
            notes: notes || null,
            createdAt: new Date().toISOString(),
        };

        await db.insert(retentionPolicies).values(newPolicy);
        return NextResponse.json(newPolicy, { status: 201 });
    } catch (error) {
        console.error('POST /api/retention error:', error);
        return NextResponse.json({ error: 'Failed to create retention policy' }, { status: 500 });
    }
}
