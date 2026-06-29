import { NextResponse } from 'next/server';
import { db } from '@/db';
import { userCompetencies, users } from '@/db/schema';
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

// GET /api/competency — list competency records joined with user names
// Query: ?userId=xxx&status=Active
export async function GET(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    try {
        const { searchParams } = new URL(request.url);
        const userIdFilter = searchParams.get('userId');
        const statusFilter = searchParams.get('status');

        let records = await db.select().from(userCompetencies);

        if (userIdFilter) {
            records = records.filter(r => r.userId === userIdFilter);
        }
        if (statusFilter) {
            records = records.filter(r => r.status === statusFilter);
        }

        // Enrich with user names
        const allUsers = await db.select({ id: users.id, name: users.name, username: users.username, department: users.department }).from(users);
        const userMap = new Map(allUsers.map(u => [u.id, u]));

        const enriched = records.map(r => ({
            ...r,
            userName: userMap.get(r.userId)?.name || r.userId,
            userUsername: userMap.get(r.userId)?.username || '',
            userDepartment: userMap.get(r.userId)?.department || '',
        }));

        return NextResponse.json(enriched);
    } catch (error) {
        console.error('GET /api/competency error:', error);
        return NextResponse.json({ error: 'Failed to fetch competency records' }, { status: 500 });
    }
}

// POST /api/competency — create competency record (manager/admin only)
export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { userId, testId, category, competencyDate, expiryDate, notes } = body;

        if (!userId || !competencyDate || !expiryDate) {
            return NextResponse.json({ error: 'userId, competencyDate, and expiryDate are required' }, { status: 400 });
        }

        const newRecord = {
            id: uuidv4(),
            userId,
            testId: testId || null,
            category: category || null,
            competencyDate,
            expiryDate,
            assessedBy: currentUser.username,
            status: 'Active' as const,
            notes: notes || null,
            createdAt: new Date().toISOString(),
        };

        await db.insert(userCompetencies).values(newRecord);
        return NextResponse.json(newRecord, { status: 201 });
    } catch (error) {
        console.error('POST /api/competency error:', error);
        return NextResponse.json({ error: 'Failed to create competency record' }, { status: 500 });
    }
}
