import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { db as drizzleDb } from '@/db';
import { recordLocks } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';

const LOCK_DURATION_MS = 2 * 60 * 1000; // 2 minutes (heartbeat)
const CHECKOUT_DURATION_MS = 2 * 60 * 1000; // 2 minutes (heartbeat)
const CHECKOUT_WARNING_MS = 4 * 60 * 60 * 1000; // 4 hours warning threshold

// Helper to clean expired locks
function cleanExpiredLocks(db: any): void {
    if (!db.recordLocks) db.recordLocks = [];
    const now = new Date().getTime();
    db.recordLocks = db.recordLocks.filter((lock: any) => {
        const expiresAt = new Date(lock.expiresAt).getTime();
        return expiresAt > now;
    });
}

// GET: Check lock status for a record
export async function GET(request: Request) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        const currentUser = JSON.parse(session.value);

        const { searchParams } = new URL(request.url);
        const recordType = searchParams.get('recordType');
        const recordId = searchParams.get('recordId');
        const listAll = searchParams.get('all') === 'true';

        const db = await readDb();
        cleanExpiredLocks(db);

        // Admin: List all locks
        if (listAll) {
            if (currentUser.role !== 'admin' && currentUser.role !== 'manager') {
                return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
            }
            return NextResponse.json({
                locks: db.recordLocks || []
            });
        }

        if (!recordType || !recordId) {
            return NextResponse.json({ error: 'recordType and recordId are required' }, { status: 400 });
        }

        const lock = db.recordLocks.find((l: any) =>
            l.entityType === recordType && l.entityId === recordId
        );

        if (lock) {
            return NextResponse.json({
                locked: true,
                lock
            });
        } else {
            return NextResponse.json({
                locked: false,
                lock: null
            });
        }
    } catch (error) {
        console.error('Error checking lock:', error);
        return NextResponse.json({ error: 'Failed to check lock status' }, { status: 500 });
    }
}

// POST: Checkout, checkin, or legacy acquire/release
export async function POST(request: Request) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const currentUser = JSON.parse(session.value);
        const body = await request.json();
        const { action, recordType, recordId, reason, comment } = body;

        if (!action || !recordType || !recordId) {
            return NextResponse.json({ error: 'action, recordType, and recordId are required' }, { status: 400 });
        }

        const db = await readDb();
        if (!db.recordLocks) db.recordLocks = [];
        if (!db.auditLogs) db.auditLogs = [];

        cleanExpiredLocks(db);

        // CHECKOUT: Explicit check-out for editing
        if (action === 'checkout') {
            const existingLock = db.recordLocks.find((l: any) =>
                l.recordType === recordType && l.recordId === recordId
            );

            if (existingLock) {
                if (existingLock.userId === currentUser.username) {
                    // Already checked out by this user, extend it
                    existingLock.expiresAt = new Date(Date.now() + CHECKOUT_DURATION_MS).getTime();
                    // existingLock.checkoutType = 'explicit'; // removed
                    await writeDb(db);
                    return NextResponse.json({
                        success: true,
                        checkout: existingLock,
                        message: 'Checkout extended'
                    });
                } else {
                    return NextResponse.json({
                        success: false,
                        error: `Record is checked out by ${existingLock.username}`,
                        checkout: existingLock
                    }, { status: 409 });
                }
            }

            const newCheckout = {
                id: `checkout-${Date.now()}`,
                entityType: recordType,
                entityId: recordId,
                userId: currentUser.username,
                username: currentUser.name || currentUser.username,
                // checkoutType: 'explicit', // Not in schema
                timestamp: new Date().toISOString(),
                expiresAt: new Date(Date.now() + CHECKOUT_DURATION_MS).getTime(),
                // checkoutReason: reason || '', // Not in schema
                // warningShown: false // Not in schema
            };

            db.recordLocks.push(newCheckout);
            await writeDb(db);
            await logAudit(null, recordType, recordId, 'CHECKOUT', null, { reason: reason || null }, currentUser.username);

            return NextResponse.json({
                success: true,
                checkout: newCheckout,
                message: 'Record checked out successfully'
            }, { status: 201 });
        }

        // CHECKIN: Check in record and release lock
        else if (action === 'checkin') {
            const lockIndex = db.recordLocks.findIndex((l: any) =>
                l.entityType === recordType && l.entityId === recordId
            );

            if (lockIndex === -1) {
                return NextResponse.json({
                    success: true,
                    message: 'No checkout to release'
                });
            }

            const lock = db.recordLocks[lockIndex];

            if (lock.userId !== currentUser.username && currentUser.role !== 'admin') {
                return NextResponse.json({
                    error: 'You can only check in your own checkouts'
                }, { status: 403 });
            }

            await drizzleDb.delete(recordLocks).where(eq(recordLocks.id, lock.id));
            await logAudit(null, recordType, recordId, 'CHECKIN', null, null, currentUser.username);

            return NextResponse.json({
                success: true,
                message: 'Record checked in successfully',
                // duration: `${durationHours}h ${durationMinutes}m`
            });
        }

        // FORCE-CHECKIN: Admin override
        else if (action === 'force-checkin') {
            if (currentUser.role !== 'admin') {
                return NextResponse.json({
                    error: 'Only administrators can force check-in'
                }, { status: 403 });
            }

            if (!reason) {
                return NextResponse.json({
                    error: 'Reason is required for force check-in'
                }, { status: 400 });
            }

            const lockIndex = db.recordLocks.findIndex((l: any) =>
                l.entityType === recordType && l.entityId === recordId
            );

            if (lockIndex === -1) {
                return NextResponse.json({
                    success: true,
                    message: 'No checkout found'
                });
            }

            const lock = db.recordLocks[lockIndex];
            const originalUser = lock.username;

            await drizzleDb.delete(recordLocks).where(eq(recordLocks.id, lock.id));
            await logAudit(null, recordType, recordId, 'FORCE_CHECKIN', null, { reason, originalUser }, currentUser.username);

            return NextResponse.json({
                success: true,
                message: 'Record forcibly checked in',
                originalUser
            });
        }

        // Legacy support - map to new actions
        else if (action === 'acquire' || action === 'release') {
            const newAction = action === 'acquire' ? 'checkout' : 'checkin';
            const newBody = { ...body, action: newAction };

            return POST(new Request(request.url, {
                method: 'POST',
                headers: request.headers,
                body: JSON.stringify(newBody)
            }));
        }

        else {
            return NextResponse.json({
                error: 'Invalid action. Use "checkout", "checkin", or "force-checkin"'
            }, { status: 400 });
        }

    } catch (error) {
        console.error('Error managing checkout:', error);
        return NextResponse.json({ error: 'Failed to manage checkout' }, { status: 500 });
    }
}

// DELETE: Force release lock (admin only) - kept for backward compatibility
export async function DELETE(request: Request) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const currentUser = JSON.parse(session.value);

        if (currentUser.role !== 'admin') {
            return NextResponse.json({ error: 'Forbidden: Only admins can force-release locks' }, { status: 403 });
        }

        const { searchParams } = new URL(request.url);
        const recordType = searchParams.get('recordType');
        const recordId = searchParams.get('recordId');
        const reason = searchParams.get('reason') || 'Forced by admin';

        if (!recordType || !recordId) {
            return NextResponse.json({ error: 'recordType and recordId are required' }, { status: 400 });
        }

        const db = await readDb();
        if (!db.recordLocks) db.recordLocks = [];
        if (!db.auditLogs) db.auditLogs = [];

        const lockIndex = db.recordLocks.findIndex((l: any) =>
            l.recordType === recordType && l.recordId === recordId
        );

        if (lockIndex === -1) {
            return NextResponse.json({ message: 'No lock found to release' });
        }

        const lock = db.recordLocks[lockIndex];

        await drizzleDb.delete(recordLocks).where(eq(recordLocks.id, lock.id));
        await logAudit(null, recordType, recordId, 'FORCE_RELEASE', null, { reason, originalOwner: lock.username }, currentUser.username);

        return NextResponse.json({
            success: true,
            message: 'Lock forcibly released'
        });

    } catch (error) {
        console.error('Error force-releasing lock:', error);
        return NextResponse.json({ error: 'Failed to force-release lock' }, { status: 500 });
    }
}
