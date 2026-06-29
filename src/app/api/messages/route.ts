import { NextResponse } from 'next/server';
import { db } from '@/db';
import { messages, users } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

async function getCurrentUser() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return null;
    try { return JSON.parse(session.value); } catch { return null; }
}

export async function GET() {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const rows = await db.select().from(messages)
        .where(eq(messages.recipient, currentUser.username));

    rows.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

    return NextResponse.json(rows);
}

export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const body = await request.json();
    const { toUser, toDepartment, content } = body;

    if (!content) return NextResponse.json({ error: 'Message content is required' }, { status: 400 });

    const createMsg = (recipient: string) => ({
        id: uuidv4(),
        sender: currentUser.username,
        recipient,
        subject: String(content).substring(0, 100),
        body: String(content),
        read: false,
        timestamp: new Date().toISOString(),
    });

    if (toDepartment) {
        const departmentUsers = await db.select({ username: users.username })
            .from(users)
            .where(eq(users.department, toDepartment));

        if (!departmentUsers.length) {
            return NextResponse.json({ error: 'No users found in that department' }, { status: 404 });
        }

        const newMessages = departmentUsers.map(u => createMsg(u.username));
        await db.insert(messages).values(newMessages);
        return NextResponse.json({ success: true, count: newMessages.length });

    } else if (toUser) {
        const newMessage = createMsg(toUser);
        await db.insert(messages).values(newMessage);
        return NextResponse.json(newMessage);
    }

    return NextResponse.json({ error: 'Missing recipient' }, { status: 400 });
}

export async function PUT(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const body = await request.json();
    const { id, action } = body;

    if (!id) return NextResponse.json({ error: 'id is required' }, { status: 400 });

    if (action === 'mark_read') {
        await db.update(messages).set({ read: true }).where(eq(messages.id, id));
    } else if (action === 'delete') {
        await db.delete(messages).where(eq(messages.id, id));
    }

    return NextResponse.json({ success: true });
}
