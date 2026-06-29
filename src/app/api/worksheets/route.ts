import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const db = await readDb();
    const worksheets = db.worksheets || [];
    return NextResponse.json(worksheets.sort((a: any, b: any) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()));
}

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const db = await readDb();

        const newWorksheet = {
            id: Date.now().toString(),
            status: 'Open', // Open, Closed, Sent to Analyzer
            createdAt: new Date().toISOString(),
            ...body
        };

        if (!db.worksheets) db.worksheets = [];
        db.worksheets.push(newWorksheet);

        // Audit Log
        if (!db.auditLogs) db.auditLogs = [];
        db.auditLogs.push({
            id: Date.now().toString(),
            entityType: 'Worksheet',
            entityId: newWorksheet.id,
            action: 'CREATE',
            diff: `Worksheet '${newWorksheet.name}' created by ${body.createdBy}`,
            userId: body.createdBy,
            timestamp: new Date().toISOString()
        });

        await writeDb(db);

        return NextResponse.json(newWorksheet, { status: 201 });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to create worksheet' }, { status: 500 });
    }
}

export async function PUT(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const { id, updates } = body;

        const db = await readDb();
        const index = db.worksheets?.findIndex((w: any) => w.id === id);

        if (index === undefined || index === -1) {
            return NextResponse.json({ error: 'Worksheet not found' }, { status: 404 });
        }

        const oldWs = { ...db.worksheets[index] };
        const newWs = { ...oldWs, ...updates };

        db.worksheets[index] = newWs;
        await writeDb(db);

        return NextResponse.json(newWs);
    } catch (error) {
        return NextResponse.json({ error: 'Failed to update worksheet' }, { status: 500 });
    }
}

export async function DELETE(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const id = searchParams.get('id');

        const db = await readDb();
        if (!db.worksheets) return NextResponse.json({ error: 'Not found' }, { status: 404 });

        const index = db.worksheets.findIndex((w: any) => w.id === id);
        if (index === -1) return NextResponse.json({ error: 'Not found' }, { status: 404 });

        db.worksheets.splice(index, 1);
        await writeDb(db);

        return NextResponse.json({ success: true });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to delete' }, { status: 500 });
    }
}
