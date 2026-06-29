import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { db } from '@/db';
import { sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';

export async function GET() {
    const cookieStore = await cookies();
    const token = cookieStore.get('auth_token')?.value;

    if (!token) {
        return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
    }

    try {
        // Find session
        const sessionResult = await db.select()
            .from(sessions)
            .where(eq(sessions.token, token))
            .limit(1);

        const session = sessionResult[0];

        if (!session || session.expiresAt < Date.now()) {
            return NextResponse.json({ error: 'Session expired' }, { status: 401 });
        }

        // Get user details
        const userResult = await db.select()
            .from(users)
            .where(eq(users.id, session.userId))
            .limit(1);

        const user = userResult[0];

        if (!user) {
            return NextResponse.json({ error: 'User not found' }, { status: 401 });
        }

        // Return user profile (exclude password)
        const { password: _, ...userProfile } = user;
        return NextResponse.json(userProfile);

    } catch (error) {
        console.error("Auth Check Error:", error);
        return NextResponse.json({ error: 'Invalid session' }, { status: 401 });
    }
}
