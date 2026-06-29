import { NextResponse } from 'next/server';
import { db } from '@/db';
import { notifiableConditions } from '@/db/schema';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

export async function GET() {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const conditions = await db.select().from(notifiableConditions).orderBy(notifiableConditions.name);

        const parsed = conditions.map((c) => ({
            ...c,
            testIds: c.testIds
                ? (() => { try { return JSON.parse(c.testIds!); } catch { return []; } })()
                : [],
        }));

        return NextResponse.json(parsed);
    } catch (error) {
        console.error('Notifiable conditions GET error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

export async function POST(request: Request) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        const currentUser = JSON.parse(session.value);

        if (currentUser.role !== 'admin') {
            return NextResponse.json({ error: 'Forbidden: admin only' }, { status: 403 });
        }

        const body = await request.json();
        const { name, organism, testIds, reportingBody, timeframe } = body;

        if (!name || !reportingBody) {
            return NextResponse.json({ error: 'name and reportingBody are required' }, { status: 400 });
        }

        const newCondition = {
            id: uuidv4(),
            name,
            organism: organism ?? null,
            testIds: testIds ? JSON.stringify(testIds) : null,
            reportingBody,
            timeframe: timeframe ?? '24h',
            active: true,
            createdAt: new Date().toISOString(),
        };

        await db.insert(notifiableConditions).values(newCondition);

        return NextResponse.json(
            {
                ...newCondition,
                testIds: testIds ?? [],
            },
            { status: 201 }
        );
    } catch (error) {
        console.error('Notifiable conditions POST error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
