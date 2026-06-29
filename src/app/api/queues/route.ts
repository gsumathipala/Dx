import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
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

// GET: List queues visible to current user
export async function GET() {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const dbData = await readDb();
        const allQueues = dbData.authorizationQueues || [];

        // Admins see all queues
        if (currentUser.role === 'admin') {
            return NextResponse.json(allQueues);
        }

        // Managers see only queues in their department
        if (currentUser.role === 'manager') {
            const deptQueues = allQueues.filter((q: any) => q.department === currentUser.department);
            return NextResponse.json(deptQueues);
        }

        // Others see only queues where their role is allowed AND in their department
        const visibleQueues = allQueues.filter((q: any) =>
            q.department === currentUser.department &&
            Array.isArray(q.allowedRoles) && q.allowedRoles.includes(currentUser.role)
        );

        return NextResponse.json(visibleQueues);
    } catch (error) {
        console.error('Error fetching queues:', error);
        return NextResponse.json({ error: 'Failed to fetch queues' }, { status: 500 });
    }
}

// POST: Create new queue (admin/manager only)
export async function POST(request: Request) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        // RBAC: Only admin and manager can create queues
        if (!['admin', 'manager'].includes(currentUser.role)) {
            return NextResponse.json({ error: 'Forbidden: Only admins and managers can create queues' }, { status: 403 });
        }

        const body = await request.json();
        const { name, description, department, allowedRoles } = body;

        if (!name || !name.trim()) {
            return NextResponse.json({ error: 'Queue name is required' }, { status: 400 });
        }

        if (!department || !department.trim()) {
            return NextResponse.json({ error: 'Department is required' }, { status: 400 });
        }

        // Managers can only create queues in their own department
        if (currentUser.role === 'manager' && department !== currentUser.department) {
            return NextResponse.json({ error: 'Managers can only create queues in their own department' }, { status: 403 });
        }

        const db = await readDb();
        if (!db.authorizationQueues) db.authorizationQueues = [];
        if (!db.auditLogs) db.auditLogs = [];

        // Check for duplicate queue names
        const duplicate = db.authorizationQueues.find((q: any) =>
            q.name.toLowerCase() === name.trim().toLowerCase()
        );
        if (duplicate) {
            return NextResponse.json({ error: 'Queue with this name already exists' }, { status: 409 });
        }

        const newQueue = {
            id: `queue-${Date.now()}`,
            name: name.trim(),
            description: description?.trim() || '',
            department: department.trim(),
            allowedRoles: Array.isArray(allowedRoles) ? allowedRoles : ['admin', 'manager'],
            createdBy: currentUser.username,
            createdAt: new Date().toISOString()
        };

        db.authorizationQueues.push(newQueue);

        // Audit log
        await logAudit(db, 'Queue', newQueue.id, 'CREATE', null, newQueue, currentUser.username);

        await writeDb(db);

        return NextResponse.json(newQueue, { status: 201 });
    } catch (error) {
        console.error('Error creating queue:', error);
        return NextResponse.json({ error: 'Failed to create queue' }, { status: 500 });
    }
}

// PUT: Update queue (admin/manager only)
export async function PUT(request: Request) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        // RBAC: Only admin and manager can update queues
        if (!['admin', 'manager'].includes(currentUser.role)) {
            return NextResponse.json({ error: 'Forbidden: Only admins and managers can update queues' }, { status: 403 });
        }

        const body = await request.json();
        const { id, name, description, allowedRoles } = body;

        if (!id) {
            return NextResponse.json({ error: 'Queue ID is required' }, { status: 400 });
        }

        const db = await readDb();
        if (!db.authorizationQueues) db.authorizationQueues = [];
        if (!db.auditLogs) db.auditLogs = [];

        const queueIndex = db.authorizationQueues.findIndex((q: any) => q.id === id);
        if (queueIndex === -1) {
            return NextResponse.json({ error: 'Queue not found' }, { status: 404 });
        }

        const oldQueue = { ...db.authorizationQueues[queueIndex] };
        const changes: string[] = [];

        if (name && name.trim() !== oldQueue.name) {
            // Check for duplicate names
            const duplicate = db.authorizationQueues.find((q: any, idx: number) =>
                idx !== queueIndex && q.name.toLowerCase() === name.trim().toLowerCase()
            );
            if (duplicate) {
                return NextResponse.json({ error: 'Queue with this name already exists' }, { status: 409 });
            }
            changes.push(`Name: '${oldQueue.name}' -> '${name.trim()}'`);
            db.authorizationQueues[queueIndex].name = name.trim();
        }

        if (description !== undefined && description.trim() !== oldQueue.description) {
            changes.push(`Description: '${oldQueue.description}' -> '${description.trim()}'`);
            db.authorizationQueues[queueIndex].description = description.trim();
        }

        if (allowedRoles !== undefined) {
            // Compare arrays broadly
            const oldRoles = (oldQueue.allowedRoles || []).sort().join(',');
            const newRoles = (allowedRoles || []).sort().join(',');
            if (oldRoles !== newRoles) {
                changes.push(`Roles: [${oldRoles}] -> [${newRoles}]`);
                db.authorizationQueues[queueIndex].allowedRoles = allowedRoles;
            }
        }

        if (changes.length > 0) {
            // Audit log
            await logAudit(db, 'Queue', id, 'UPDATE', oldQueue, db.authorizationQueues[queueIndex], currentUser.username);

            await writeDb(db);
        }

        return NextResponse.json(db.authorizationQueues[queueIndex]);
    } catch (error) {
        console.error('Error updating queue:', error);
        return NextResponse.json({ error: 'Failed to update queue' }, { status: 500 });
    }
}

// DELETE: Delete queue (admin/manager only)
export async function DELETE(request: Request) {
    try {
        const currentUser = await getAuthenticatedUser();
        if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        // RBAC: Only admin and manager can delete queues
        if (!['admin', 'manager'].includes(currentUser.role)) {
            return NextResponse.json({ error: 'Forbidden: Only admins and managers can delete queues' }, { status: 403 });
        }

        const { searchParams } = new URL(request.url);
        const id = searchParams.get('id');

        if (!id) {
            return NextResponse.json({ error: 'Queue ID is required' }, { status: 400 });
        }

        const db = await readDb();
        if (!db.authorizationQueues) db.authorizationQueues = [];
        if (!db.auditLogs) db.auditLogs = [];

        const queueIndex = db.authorizationQueues.findIndex((q: any) => q.id === id);
        if (queueIndex === -1) {
            return NextResponse.json({ error: 'Queue not found' }, { status: 404 });
        }

        // Check if any orders are in this queue
        const ordersInQueue = (db.orders || []).filter((o: any) => o.queueId === id);
        if (ordersInQueue.length > 0) {
            return NextResponse.json({
                error: `Cannot delete queue: ${ordersInQueue.length} result(s) are currently assigned to this queue`
            }, { status: 409 });
        }

        const deletedQueue = db.authorizationQueues[queueIndex];
        db.authorizationQueues.splice(queueIndex, 1);

        // Audit log
        await logAudit(db, 'Queue', id, 'DELETE', deletedQueue, null, currentUser.username);

        await writeDb(db);

        return NextResponse.json({ message: 'Queue deleted successfully' });
    } catch (error) {
        console.error('Error deleting queue:', error);
        return NextResponse.json({ error: 'Failed to delete queue' }, { status: 500 });
    }
}
