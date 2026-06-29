import { NextResponse } from 'next/server';
import { db } from '@/db';
import { deltaCheckRules } from '@/db/schema';
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

// GET /api/delta-checks/rules — returns all rules
export async function GET() {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const rules = await db.select().from(deltaCheckRules);
        return NextResponse.json(rules);
    } catch (error) {
        console.error('GET delta-check rules error:', error);
        return NextResponse.json({ error: 'Failed to fetch delta check rules' }, { status: 500 });
    }
}

// POST /api/delta-checks/rules — create a rule (manager/admin only)
export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden: Manager/Admin only' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { testId, testCode, deltaType, threshold, direction } = body;

        if (!testId || !testCode || !deltaType || threshold === undefined) {
            return NextResponse.json({ error: 'Missing required fields: testId, testCode, deltaType, threshold' }, { status: 400 });
        }
        if (!['percent', 'absolute'].includes(deltaType)) {
            return NextResponse.json({ error: 'deltaType must be "percent" or "absolute"' }, { status: 400 });
        }
        if (!['any', 'increase', 'decrease'].includes(direction || 'any')) {
            return NextResponse.json({ error: 'direction must be "any", "increase", or "decrease"' }, { status: 400 });
        }

        const newRule = {
            id: uuidv4(),
            testId,
            testCode,
            deltaType,
            threshold: Number(threshold),
            direction: direction || 'any',
            enabled: true,
            createdAt: new Date().toISOString(),
            createdBy: currentUser.username,
        };

        await db.insert(deltaCheckRules).values(newRule);
        return NextResponse.json(newRule, { status: 201 });
    } catch (error) {
        console.error('POST delta-check rule error:', error);
        return NextResponse.json({ error: 'Failed to create delta check rule' }, { status: 500 });
    }
}
