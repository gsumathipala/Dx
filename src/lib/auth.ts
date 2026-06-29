/**
 * Unified auth helper — resolves a user from either the session-token
 * cookie (auth_token → sessions table) or the legacy JSON cookie (auth_session).
 * Both cookies are set on login so all routes work regardless of which pattern
 * they were written with.
 */
import { db } from '@/db';
import { sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';

export interface AuthUser {
    id: string;
    username: string;
    role: string;
    name: string;
    department: string | null;
    email: string | null;
}

export async function getAuthUser(): Promise<AuthUser | null> {
    try {
        const cookieStore = await cookies();

        // Primary: token-based session (auth_token → sessions table)
        const token = cookieStore.get('auth_token')?.value;
        if (token) {
            const sessionRows = await db.select().from(sessions).where(eq(sessions.token, token)).limit(1);
            const session = sessionRows[0];
            if (session && session.expiresAt > Date.now()) {
                const userRows = await db.select().from(users).where(eq(users.id, session.userId)).limit(1);
                if (userRows[0]) {
                    const { password: _, ...u } = userRows[0];
                    return u as AuthUser;
                }
            }
        }

        // Fallback: legacy JSON cookie (auth_session)
        const sessionCookie = cookieStore.get('auth_session');
        if (sessionCookie?.value) {
            try {
                const parsed = JSON.parse(sessionCookie.value);
                if (parsed?.username) return parsed as AuthUser;
            } catch { /* ignore */ }
        }

        return null;
    } catch {
        return null;
    }
}

export function requireRole(user: AuthUser | null, roles: string[]): boolean {
    return user !== null && roles.includes(user.role);
}
