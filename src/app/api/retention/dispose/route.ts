import { NextResponse } from 'next/server';
import { db } from '@/db';
import { specimens, retentionPolicies, specimenDisposals } from '@/db/schema';
import { eq, inArray } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

async function getCurrentUser() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return null;
    try {
        return JSON.parse(session.value);
    } catch {
        return null;
    }
}

// POST /api/retention/dispose — batch disposal
export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { specimenIds, notes, batchNumber } = body as {
            specimenIds: string[];
            notes?: string;
            batchNumber?: string;
        };

        if (!specimenIds || !Array.isArray(specimenIds) || specimenIds.length === 0) {
            return NextResponse.json({ error: 'specimenIds array is required' }, { status: 400 });
        }

        // Load all policies once
        const allPolicies = await db.select().from(retentionPolicies);

        // Load the target specimens
        const targetSpecimens = await db.select().from(specimens).where(inArray(specimens.id, specimenIds));

        const now = new Date().toISOString();
        const generatedBatch = batchNumber || `DISP-${Date.now()}`;
        let disposed = 0;

        for (const specimen of targetSpecimens) {
            // Find matching retention policy by specimen type
            const policy = allPolicies.find(
                p => p.specimenType.toLowerCase() === (specimen.type || '').toLowerCase() && p.active
            );

            const disposal = {
                id: uuidv4(),
                specimenId: specimen.id,
                policyId: policy?.id || null,
                disposedAt: now,
                disposedBy: currentUser.username,
                batchNumber: generatedBatch,
                notes: notes || null,
            };

            await db.insert(specimenDisposals).values(disposal);
            await db.update(specimens).set({ status: 'Disposed' }).where(eq(specimens.id, specimen.id));
            disposed++;
        }

        return NextResponse.json({ disposed, batchNumber: generatedBatch });
    } catch (error) {
        console.error('POST /api/retention/dispose error:', error);
        return NextResponse.json({ error: 'Failed to process disposal batch' }, { status: 500 });
    }
}
