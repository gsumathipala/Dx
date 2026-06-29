import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';
import { getAuthUser } from '@/lib/auth';

export async function GET() {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const db = await readDb();
    return NextResponse.json(db.inventory || []);
}

export async function POST(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const user = JSON.parse(session.value);

    // RBAC
    if (!['admin', 'manager'].includes(user.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    const body = await request.json();
    const db = await readDb();
    if (!db.inventory) db.inventory = [];

    const newItem = {
        id: uuidv4(),
        name: body.name,
        lotNumber: body.lotNumber,
        expirationDate: body.expiry, // YYYY-MM-DD
        quantity: Number(body.quantity),
        unit: body.unit, // 'kits', 'boxes', 'liters'
        location: body.location || null,
        minThreshold: Number(body.minLevel) || 10,
    };

    db.inventory.push(newItem);
    await writeDb(db);
    await logAudit(db, 'Inventory', newItem.id, 'CREATE', null, newItem, user.username);

    return NextResponse.json(newItem, { status: 201 });
}

export async function PUT(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    // Update stock levels logic...
    const body = await request.json();
    const db = await readDb();
    if (!db.inventory) return NextResponse.json({ error: 'No inventory' }, { status: 404 });

    const idx = db.inventory.findIndex((i: any) => i.id === body.id);
    if (idx === -1) return NextResponse.json({ error: 'Not found' }, { status: 404 });

    db.inventory[idx] = { ...db.inventory[idx], ...body.updates };
    await writeDb(db);

    return NextResponse.json({ success: true });
}
