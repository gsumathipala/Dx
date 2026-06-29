import { NextResponse } from 'next/server';
import { db } from '@/db';
import { distributionRules, requesters } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

export async function GET() {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const rules = await db.select().from(distributionRules).orderBy(distributionRules.createdAt);
        const allRequesters = await db.select().from(requesters);
        const requesterMap = new Map(allRequesters.map((r) => [r.id, r.name]));

        const enriched = rules.map((rule) => ({
            ...rule,
            requesterName: rule.requesterId ? (requesterMap.get(rule.requesterId) ?? 'Unknown') : 'All Requesters',
        }));

        return NextResponse.json(enriched);
    } catch (error) {
        console.error('Distribution rules GET error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

export async function POST(request: Request) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        const currentUser = JSON.parse(session.value);

        if (!['manager', 'admin'].includes(currentUser.role)) {
            return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
        }

        const body = await request.json();
        const { requesterId, testId, method, destination, autoRelease } = body;

        if (!method) {
            return NextResponse.json({ error: 'method is required' }, { status: 400 });
        }

        const newRule = {
            id: uuidv4(),
            requesterId: requesterId ?? null,
            testId: testId ?? null,
            method,
            destination: destination ?? null,
            autoRelease: autoRelease ?? false,
            active: true,
            createdAt: new Date().toISOString(),
        };

        await db.insert(distributionRules).values(newRule);

        return NextResponse.json(newRule, { status: 201 });
    } catch (error) {
        console.error('Distribution rules POST error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
