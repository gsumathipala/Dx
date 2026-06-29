import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import { db } from '@/db';
import { tatThresholds, sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

async function getAuthenticatedUser() {
    const cookieStore = await cookies();
    const token = cookieStore.get('auth_token')?.value;
    if (!token) return null;
    const sessionResult = await db.select().from(sessions).where(eq(sessions.token, token)).limit(1);
    const session = sessionResult[0];
    if (!session || session.expiresAt < Date.now()) return null;
    const userResult = await db.select().from(users).where(eq(users.id, session.userId)).limit(1);
    return userResult[0] || null;
}

export async function GET() {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const thresholds = await db.select().from(tatThresholds);
        return NextResponse.json(thresholds);
    } catch (error) {
        console.error('GET /api/tat-thresholds error:', error);
        return NextResponse.json({ error: 'Failed to fetch TAT thresholds', details: String(error) }, { status: 500 });
    }
}

export async function POST(request: Request) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        if (!['manager', 'admin', 'labmanager', 'supervisor'].includes(currentUser.role?.toLowerCase())) {
            return NextResponse.json({ error: 'Forbidden: Manager or Admin role required' }, { status: 403 });
        }

        const body = await request.json();
        const { scope, scopeId, targetHours, warningHours, breachHours, priority } = body;

        if (!scope || !targetHours || !warningHours || !breachHours) {
            return NextResponse.json({ error: 'scope, targetHours, warningHours, and breachHours are required' }, { status: 400 });
        }

        const id = uuidv4();
        await db.insert(tatThresholds).values({
            id,
            scope,
            scopeId: scopeId || null,
            targetHours: Number(targetHours),
            warningHours: Number(warningHours),
            breachHours: Number(breachHours),
            priority: priority || 'Routine',
            active: true,
            createdAt: new Date().toISOString(),
        });

        return NextResponse.json({ id }, { status: 201 });
    } catch (error) {
        console.error('POST /api/tat-thresholds error:', error);
        return NextResponse.json({ error: 'Failed to create TAT threshold', details: String(error) }, { status: 500 });
    }
}
