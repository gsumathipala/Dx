import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET() {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const db = await readDb();
    return NextResponse.json(db.feedback || []);
}

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const db = await readDb();

        if (!db.feedback) db.feedback = [];

        const newItem = {
            id: Date.now().toString(),
            date: new Date().toISOString(),
            status: 'Open',
            ...body
        };

        db.feedback.push(newItem);
        await writeDb(db);

        return NextResponse.json(newItem);
    } catch (error) {
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}

export async function PUT(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    try {
        const body = await request.json();
        const { id, ...updates } = body;
        const db = await readDb();

        if (db.feedback) {
            db.feedback = db.feedback.map((item: any) =>
                item.id === id ? { ...item, ...updates } : item
            );
            await writeDb(db);
        }

        return NextResponse.json({ success: true });
    } catch (error) {
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}
