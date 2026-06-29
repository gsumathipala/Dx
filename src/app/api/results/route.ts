import { NextResponse } from 'next/server';
import { db } from '@/db';
import { results, users, orders, auditLogs, resultSignatures } from '@/db/schema';
import { eq, and } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';
import { consumeReagent } from '@/lib/inventory';
import { runDeltaChecks, checkCriticalValues, evaluateReflexRules, checkNotifiableConditions } from '@/lib/clinical-engine';

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const orderId = searchParams.get('orderId');

    try {
        // Drizzle doesn't support easy dynamic queries for multiple optional filters without helper builder
        // For now, orderId is the main use case
        if (!orderId) return NextResponse.json([]);

        const rows = await db.select().from(results).where(eq(results.orderId, orderId));

        // Transform back to legacy format for frontend if needed?
        // Frontend expects "Result Sets" (one object with values logic?)
        // Or does it handle list of results?
        // Let's return list of rows, assuming frontend can map.
        // Actually, existing frontend expects ONE result object per order probably? 
        // "existingResultIndex = db.results.findIndex(r => r.orderId === orderId)" suggests 1:1 Order:ResultObject mapping in legacy.

        // We will reconstruct the Legacy Object structure from the atomic rows
        // to avoid breaking frontend.

        if (rows.length === 0) return NextResponse.json([]);

        const compositeResult = {
            id: rows[0].orderId + '-report',
            orderId: rows[0].orderId,
            status: rows[0].status,
            values: {
                results: rows.reduce((acc, row) => {
                    if (row.testId !== 'REPORT') {
                        try {
                            const parsed = JSON.parse(row.values || '{}');
                            acc[row.testId] = parsed.value || '';
                        } catch {
                            acc[row.testId] = '';
                        }
                    }
                    return acc;
                }, {} as any),
                notes: rows.find(r => r.testId === 'REPORT')?.comments || '' // Mapping back logic
            },
            verifiedBy: rows[0].clinicalVerifiedBy,
            releasedBy: rows[0].clinicalVerifiedBy
        };

        // Return array of this single composite object to match legacy "results.filter" return type
        return NextResponse.json([compositeResult]);

    } catch (error) {
        console.error('Fetch results error:', error);
        return NextResponse.json({ error: 'Failed to fetch results' }, { status: 500 });
    }
}

export async function POST(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const currentUser = JSON.parse(session.value);

    try {
        const body = await request.json();
        const { orderId, values, status, action, reason } = body;

        // Fetch User for RBAC (can optimize to trust session for now)
        // const user = await db.select().from(users)...

        // Calculate Status
        let statusToSet = status || 'Resulted';
        if (action === 'TECHNICAL_VALIDATE') statusToSet = 'Technically Validated';
        if (action === 'CLINICAL_VERIFY') statusToSet = 'Clinically Verified';

        // 1. Process Atomic Results
        const resultsMap = values?.results || {};
        for (const [testId, val] of Object.entries(resultsMap)) {
            // Delete existing for this test? Or Upsert.
            // SQLite upsert: insert ... on conflict ...
            // But we don't have unique constraint on (orderId, testId) in schema yet.
            // We should find and update or insert.

            const existing = await db.select().from(results).where(
                and(eq(results.orderId, orderId), eq(results.testId, testId))
            ).limit(1);

            if (existing.length > 0) {
                await db.update(results).set({
                    values: JSON.stringify({ value: String(val) }),
                    status: statusToSet,
                    technicalValidatedBy: action === 'TECHNICAL_VALIDATE' ? currentUser.username : existing[0].technicalValidatedBy,
                    clinicalVerifiedBy: action === 'CLINICAL_VERIFY' ? currentUser.username : existing[0].clinicalVerifiedBy
                }).where(eq(results.id, existing[0].id));
            } else {
                await db.insert(results).values({
                    id: uuidv4(),
                    orderId,
                    testId,
                    values: JSON.stringify({ value: String(val) }),
                    status: statusToSet,
                    technicalValidatedBy: action === 'TECHNICAL_VALIDATE' ? currentUser.username : null,
                    clinicalVerifiedBy: action === 'CLINICAL_VERIFY' ? currentUser.username : null,
                    timestamp: new Date().toISOString()
                });

                // Track Inventory Usage (New Result = 1 Test Used)
                await consumeReagent(testId, currentUser.username).catch(err => console.error(`Inventory error for ${testId}:`, err));
            }

            // ── Clinical Engine (runs on initial result entry, not re-validation) ──
            if (action !== 'TECHNICAL_VALIDATE' && action !== 'CLINICAL_VERIFY') {
                const orderRows = await db.select({ patientId: orders.patientId })
                    .from(orders).where(eq(orders.id, orderId)).limit(1);
                const patientId = orderRows[0]?.patientId;
                if (patientId) {
                    const numVal = parseFloat(String(val));
                    if (!isNaN(numVal)) {
                        // Delta checks
                        runDeltaChecks(orderId, patientId, testId, numVal)
                            .catch(e => console.error('Delta check failed:', e));
                        // Critical values
                        checkCriticalValues(orderId, patientId, testId, testId, numVal, currentUser.username)
                            .catch(e => console.error('Critical value check failed:', e));
                        // Reflex rules
                        evaluateReflexRules(orderId, testId, numVal)
                            .catch(e => console.error('Reflex rule eval failed:', e));
                    }
                    // Notifiable disease surveillance (any result type, incl. qualitative)
                    checkNotifiableConditions(orderId, patientId, testId)
                        .catch(e => console.error('Notifiable condition check failed:', e));
                }
            }
        }

        // 2. Process "Report Level" data (notes, comments) as a pseudo result
        // This preserves the `values.notes` etc
        const reportNotes = values?.notes || values?.internalComments;
        if (reportNotes) {
            // Upsert "REPORT" testId
            const existingRep = await db.select().from(results).where(
                and(eq(results.orderId, orderId), eq(results.testId, 'REPORT'))
            ).limit(1);

            if (existingRep.length > 0) {
                await db.update(results).set({ comments: reportNotes }).where(eq(results.id, existingRep[0].id));
            } else {
                await db.insert(results).values({
                    id: uuidv4(),
                    orderId,
                    testId: 'REPORT',
                    values: null,
                    comments: reportNotes,
                    status: statusToSet,
                    timestamp: new Date().toISOString()
                });
            }
        }

        // 3. Update Order Status in SQLite (single source of truth)
        const now = new Date().toISOString();
        const orderUpdate: Record<string, any> = { updatedAt: now };

        if (statusToSet === 'Clinically Verified') {
            orderUpdate.status = 'Completed';
            orderUpdate.completedAt = now;
        } else {
            orderUpdate.status = statusToSet;
        }
        if (body.queueId) {
            orderUpdate.queueId = body.queueId;
        }

        await db.update(orders).set(orderUpdate).where(eq(orders.id, orderId));

        // Record electronic signature for validation actions (shown on printed reports)
        if (action === 'TECHNICAL_VALIDATE' || action === 'CLINICAL_VERIFY') {
            await db.insert(resultSignatures).values({
                id: uuidv4(),
                orderId,
                signedBy: currentUser.name || currentUser.username,
                signedAt: now,
                signatureType: action === 'CLINICAL_VERIFY' ? 'clinical' : 'technical',
                ipAddress: request.headers.get('x-forwarded-for') || null,
                userAgent: request.headers.get('user-agent') || null
            });
        }

        // 4. Audit Log
        await db.insert(auditLogs).values({
            id: uuidv4(),
            entityType: 'Result',
            entityId: orderId, // Tracking by order ID largely
            action: action || 'UPDATE',
            userId: currentUser.username,
            details: `Status: ${statusToSet} | Queue: ${body.queueId || 'Unchanged'}`,
            timestamp: new Date().toISOString()
        });

        return NextResponse.json({ success: true }, { status: 200 });

    } catch (error) {
        console.error('Result save error:', error);
        return NextResponse.json({ error: 'Failed to save result' }, { status: 500 });
    }
}
