import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { cookies } from 'next/headers';
import { db } from '@/db';
import { sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';

// Helper to get authenticated user from token
async function getAuthenticatedUser() {
    const cookieStore = await cookies();
    const token = cookieStore.get('auth_token')?.value;

    if (!token) return null;

    const sessionResult = await db.select()
        .from(sessions)
        .where(eq(sessions.token, token))
        .limit(1);

    const session = sessionResult[0];
    if (!session || session.expiresAt < Date.now()) return null;

    const userResult = await db.select()
        .from(users)
        .where(eq(users.id, session.userId))
        .limit(1);

    return userResult[0] || null;
}

// GET: List all inventory items
export async function GET() {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const dbData = await readDb();

    // Sort by expiration date (soonest first) - use correct field name
    const inventory = (dbData.inventory || []).sort((a: any, b: any) => {
        return new Date(a.expirationDate).getTime() - new Date(b.expirationDate).getTime();
    });

    return NextResponse.json(inventory);
}

// POST: Add new item
export async function POST(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const body = await request.json();
        const { name, lotNumber, expiryDate, quantity, lowStockThreshold, unit } = body;

        const dbData = await readDb();

        const newItem = {
            id: Date.now().toString(),
            name,
            lotNumber,
            expirationDate: expiryDate ? new Date(expiryDate).toISOString() : null,
            quantity: Number(quantity),
            unit,
            minThreshold: Number(lowStockThreshold),
            location: 'Main Storage' // Default
        };

        if (!dbData.inventory) dbData.inventory = [];
        dbData.inventory.push(newItem);
        await writeDb(dbData);

        return NextResponse.json(newItem, { status: 201 });
    } catch (error) {
        return NextResponse.json({ error: 'Failed to create item' }, { status: 500 });
    }
}

