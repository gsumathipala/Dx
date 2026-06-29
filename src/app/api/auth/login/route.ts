import { NextResponse } from 'next/server';
import { db } from '@/db';
import { users, sessions } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';
import bcrypt from 'bcryptjs';
import { v4 as uuidv4 } from 'uuid';

export async function POST(request: Request) {
    try {
        const body = await request.json();
        const { username, password } = body;

        const results = await db.select().from(users).where(eq(users.username, username)).limit(1);
        const user = results[0];

        if (!user) {
            return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
        }

        // Check if password is hashed (bcrypt hashes start with $2)
        const isPasswordHashed = user.password.startsWith('$2');

        let passwordValid = false;
        if (isPasswordHashed) {
            // New secure password - use bcrypt compare
            passwordValid = await bcrypt.compare(password, user.password);
        } else {
            // Legacy cleartext password - direct comparison
            // Also upgrade the password to bcrypt for future logins
            passwordValid = password === user.password;
            if (passwordValid) {
                // Upgrade to bcrypt hash
                const hashedPassword = await bcrypt.hash(password, 12);
                await db.update(users)
                    .set({ password: hashedPassword })
                    .where(eq(users.id, user.id));
            }
        }

        if (!passwordValid) {
            return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
        }

        // Create secure session
        const token = uuidv4();
        const expiresAt = Date.now() + (1000 * 60 * 60 * 24); // 24 hours

        await db.insert(sessions).values({
            id: uuidv4(),
            userId: user.id,
            token,
            expiresAt
        });

        const cookieStore = await cookies();
        const cookieOpts = {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict' as const,
            maxAge: 60 * 60 * 24 // 24 hours
        };

        // Primary: token-based session
        cookieStore.set('auth_token', token, cookieOpts);

        // Legacy JSON cookie — kept for backward compat with routes that read auth_session
        const { password: _, ...userWithoutPassword } = user;
        cookieStore.set('auth_session', JSON.stringify(userWithoutPassword), cookieOpts);

        return NextResponse.json(userWithoutPassword);
    } catch (error) {
        console.error('Login error:', error);
        return NextResponse.json({ error: 'Login failed' }, { status: 500 });
    }
}
