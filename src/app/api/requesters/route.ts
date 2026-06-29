import { NextResponse } from 'next/server';
import { db } from '@/db';
import { requesters } from '@/db/schema';
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

// GET /api/requesters — list all requesters, ?active=true to filter
export async function GET(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const activeFilter = searchParams.get('active');

        let rows = await db.select().from(requesters);

        if (activeFilter === 'true') {
            rows = rows.filter(r => r.active === true);
        } else if (activeFilter === 'false') {
            rows = rows.filter(r => r.active === false);
        }

        return NextResponse.json(rows);
    } catch (error) {
        console.error('GET /api/requesters error:', error);
        return NextResponse.json({ error: 'Failed to fetch requesters' }, { status: 500 });
    }
}

// POST /api/requesters — create a requester (manager/admin only)
export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { name, type, contactName, email, phone, fax, address, deliveryPreference, notes } = body;

        if (!name || !type) {
            return NextResponse.json({ error: 'name and type are required' }, { status: 400 });
        }

        const newRequester = {
            id: uuidv4(),
            name,
            type,
            contactName: contactName || null,
            email: email || null,
            phone: phone || null,
            fax: fax || null,
            address: address || null,
            deliveryPreference: deliveryPreference || 'portal',
            active: true,
            createdAt: new Date().toISOString(),
            notes: notes || null,
        };

        await db.insert(requesters).values(newRequester);
        return NextResponse.json(newRequester, { status: 201 });
    } catch (error) {
        console.error('POST /api/requesters error:', error);
        return NextResponse.json({ error: 'Failed to create requester' }, { status: 500 });
    }
}
