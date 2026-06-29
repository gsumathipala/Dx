import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import { readDb, writeDb } from '@/lib/db';
import { cookies } from 'next/headers';
import { db } from '@/db';
import { sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';
import bcrypt from 'bcryptjs';

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

// POST: Create a new user
export async function POST(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    if (currentUser.role !== 'admin') {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { username, password, role, name, department, email } = body;

        if (!username || !password) {
            return NextResponse.json({ error: 'Username and password required' }, { status: 400 });
        }

        const dbData = await readDb();

        // Check if user already exists
        const exists = dbData.users.find((u: any) => u.username === username);
        if (exists) {
            return NextResponse.json({ error: 'Username already exists' }, { status: 409 });
        }

        // Hash password
        const hashedPassword = await bcrypt.hash(password, 12);

        const newUser = {
            id: Date.now().toString(),
            username,
            password: hashedPassword,
            role: role || 'clerk',
            name: name || username,
            department: department || 'General',
            email: email || null
        };

        dbData.users.push(newUser);
        await writeDb(dbData);

        // Don't return password
        const { password: _, ...safeUser } = newUser;
        return NextResponse.json(safeUser, { status: 201 });

    } catch (error) {
        return NextResponse.json({ error: 'Failed to create user' }, { status: 500 });
    }
}

// GET: List all users
export async function GET(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (currentUser.role !== 'admin') return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

    const dbData = await readDb();
    const safeUsers = dbData.users.map(({ password, ...m }: any) => m); // Exclude passwords
    return NextResponse.json(safeUsers);
}

// PUT: Update user (Change Credentials)
export async function PUT(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (currentUser.role !== 'admin') return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

    try {
        const body = await request.json();
        const { id, updates } = body;
        const dbData = await readDb();
        const idx = dbData.users.findIndex((u: any) => u.id === id);

        if (idx === -1) return NextResponse.json({ error: 'User not found' }, { status: 404 });

        // If password is being updated, hash it
        if (updates.password) {
            updates.password = await bcrypt.hash(updates.password, 12);
        }

        // Update fields
        dbData.users[idx] = { ...dbData.users[idx], ...updates };
        await writeDb(dbData);

        return NextResponse.json({ message: 'User updated' });
    } catch (e) {
        return NextResponse.json({ error: 'Update failed' }, { status: 500 });
    }
}

// DELETE: Remove user
export async function DELETE(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    // RBAC: Admin or Manager
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        // Read body for password
        const body = await request.json();
        const { password } = body;

        // Read query for target ID
        const { searchParams } = new URL(request.url);
        const targetId = searchParams.get('id');

        if (!targetId) return NextResponse.json({ error: 'ID required' }, { status: 400 });
        if (!password) return NextResponse.json({ error: 'Password authorization required' }, { status: 401 });
        if (targetId === currentUser.id) return NextResponse.json({ error: 'Cannot delete yourself' }, { status: 400 });

        const dbData = await readDb();

        // 1. Verify Requesting User Password (using bcrypt)
        const requestor = dbData.users.find((u: any) => u.username === currentUser.username);
        if (!requestor) {
            return NextResponse.json({ error: 'Requestor not found' }, { status: 401 });
        }

        const passwordValid = await bcrypt.compare(password, requestor.password);
        if (!passwordValid) {
            return NextResponse.json({ error: 'Invalid password authorization' }, { status: 401 });
        }

        // 2. Perform Deletion
        const initialLen = dbData.users.length;
        dbData.users = dbData.users.filter((u: any) => u.id !== targetId);

        if (dbData.users.length === initialLen) {
            return NextResponse.json({ error: 'User not found' }, { status: 404 });
        }

        await writeDb(dbData);

        return NextResponse.json({ message: 'User deleted' });
    } catch (e) {
        return NextResponse.json({ error: 'Delete failed' }, { status: 500 });
    }
}

