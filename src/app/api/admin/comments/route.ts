import { NextResponse } from 'next/server';
import { readDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET() {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const db = await readDb();
    return NextResponse.json(db.commentCodes || []);
}
