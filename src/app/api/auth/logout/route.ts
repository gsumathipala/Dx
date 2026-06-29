import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { db } from '@/db';
import { sessions } from '@/db/schema';
import { eq } from 'drizzle-orm';

export async function POST() {
    const cookieStore = await cookies();
    const token = cookieStore.get('auth_token')?.value;

    if (token) {
        await db.delete(sessions).where(eq(sessions.token, token));
    }

    cookieStore.delete('auth_token');
    cookieStore.delete('auth_session');

    return NextResponse.json({ success: true });
}
