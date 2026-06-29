import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import { db } from '@/db';
import { resultSignatures, sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';
import bcrypt from 'bcryptjs';

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

export async function GET(request: Request) {
    const authUser = await getAuthenticatedUser();
    if (!authUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const orderId = searchParams.get('orderId');

        if (!orderId) {
            return NextResponse.json({ error: 'orderId query parameter is required' }, { status: 400 });
        }

        const sigs = await db.select().from(resultSignatures).where(eq(resultSignatures.orderId, orderId));
        return NextResponse.json(sigs);
    } catch (error) {
        console.error('GET /api/signatures error:', error);
        return NextResponse.json({ error: 'Failed to fetch signatures', details: String(error) }, { status: 500 });
    }
}

export async function POST(request: Request) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { orderId, signatureType, pin } = body;

        if (!orderId || !signatureType || !pin) {
            return NextResponse.json({ error: 'orderId, signatureType, and pin are required' }, { status: 400 });
        }

        // Validate PIN against stored password hash
        const isValid = await bcrypt.compare(String(pin), currentUser.password);
        if (!isValid) {
            return NextResponse.json({ error: 'Invalid PIN' }, { status: 403 });
        }

        // Get request metadata
        const headersList = request.headers;
        const ipAddress = headersList.get('x-forwarded-for') || headersList.get('x-real-ip') || 'unknown';
        const userAgent = headersList.get('user-agent') || 'unknown';

        const id = uuidv4();
        await db.insert(resultSignatures).values({
            id,
            orderId,
            signedBy: currentUser.username,
            signedAt: new Date().toISOString(),
            signatureType,
            ipAddress,
            userAgent,
        });

        return NextResponse.json({ id, signedBy: currentUser.username, signedAt: new Date().toISOString() }, { status: 201 });
    } catch (error) {
        console.error('POST /api/signatures error:', error);
        return NextResponse.json({ error: 'Failed to create signature', details: String(error) }, { status: 500 });
    }
}
