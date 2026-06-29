import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { cookies } from 'next/headers';

type Props = {
    params: Promise<{ id: string }>;
};

// PUT: Update item
export async function PUT(request: Request, { params }: Props) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const { id } = await params;
        const body = await request.json();
        const db = await readDb();

        const index = db.inventory.findIndex((i: any) => i.id === id);
        if (index === -1) {
            return NextResponse.json({ error: 'Item not found' }, { status: 404 });
        }

        db.inventory[index] = { ...db.inventory[index], ...body };
        await writeDb(db);

        return NextResponse.json(db.inventory[index]);
    } catch (error) {
        return NextResponse.json({ error: 'Failed to update item' }, { status: 500 });
    }
}

// DELETE: Remove item
export async function DELETE(request: Request, { params }: Props) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const { id } = await params;
        const db = await readDb();

        db.inventory = db.inventory.filter((i: any) => i.id !== id);
        await writeDb(db);

        return NextResponse.json({ success: true });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to delete item' }, { status: 500 });
    }
}
