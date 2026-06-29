import { NextResponse } from 'next/server';
import { readDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET() {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const db = await readDb();
    // Return minimal user info for selection (no passwords, no emails)
    const users = (db.users || []).map((u: any) => ({
        username: u.username,
        name: u.name,
        role: u.role
    }));
    return NextResponse.json(users);
}
