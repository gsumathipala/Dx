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
/**
 * Test Definitions API - APHL 2019 Compliant
 * 
 * Schema:
 * - id: string
 * - name: string
 * - code: string (internal code)
 * - loincCode: string (LOINC interoperability)
 * - snomedCode: string (SNOMED CT for findings)
 * - units: string
 * - referenceRange: { min, max, panicLow, panicHigh, unit, text }
 * - tatHours: number
 * - department: string
 * - specimenTypes: string[] (valid specimen types)
 * - methodology: string
 * - active: boolean
 */

// GET: List all test definitions (filtered by enabled departments)
export async function GET(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized - Please log in' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const includeDisabledDepts = searchParams.get('includeDisabledDepts') === 'true';

    const dbData = await readDb();
    let tests = dbData.testDefinitions || [];

    // Filter out tests from disabled departments unless explicitly requested
    if (!includeDisabledDepts && dbData.departments) {
        const enabledDeptNames = (dbData.departments as any[])
            .filter((d: any) => d.enabled !== false)
            .map((d: any) => d.name);

        tests = tests.filter((t: any) =>
            !t.department || enabledDeptNames.includes(t.department)
        );
    }

    return NextResponse.json(tests);
}

// POST: Create new test definition
export async function POST(request: Request) {
    const currentUser = await getAuthenticatedUser();
    console.log('POST /api/admin/tests - currentUser:', currentUser ? { username: currentUser.username, role: currentUser.role } : 'null');

    if (!currentUser) {
        return NextResponse.json({ error: 'Unauthorized - Please log in' }, { status: 401 });
    }

    if (!['admin', 'manager'].includes(currentUser.role)) {
        console.log(`POST /api/admin/tests - User ${currentUser.username} has role ${currentUser.role}, not admin/manager`);
        return NextResponse.json({ error: `Forbidden: Admin/Manager only (you have: ${currentUser.role})` }, { status: 403 });
    }

    try {
        const body = await request.json();
        const {
            name,
            code,
            loincCode,
            snomedCode,
            units,
            referenceRange, // Can be string "10-20" or object { min, max, panicLow, panicHigh }
            tatHours,
            department,
            specimenTypes,
            methodology,
            price
        } = body;

        const dbData = await readDb();

        // Parse reference range into structured format
        let structuredRange = null;
        if (referenceRange) {
            if (typeof referenceRange === 'string') {
                // Parse "10-20" format
                const match = referenceRange.match(/(\d+\.?\d*)\s*-\s*(\d+\.?\d*)/);
                if (match) {
                    structuredRange = {
                        min: parseFloat(match[1]),
                        max: parseFloat(match[2]),
                        panicLow: null,
                        panicHigh: null,
                        unit: units || '',
                        text: referenceRange
                    };
                } else {
                    structuredRange = { text: referenceRange };
                }
            } else {
                // Already structured
                structuredRange = {
                    min: referenceRange.min ?? null,
                    max: referenceRange.max ?? null,
                    panicLow: referenceRange.panicLow ?? null,
                    panicHigh: referenceRange.panicHigh ?? null,
                    unit: referenceRange.unit || units || '',
                    text: referenceRange.text || `${referenceRange.min}-${referenceRange.max}`
                };
            }
        }

        if (!code) {
            return NextResponse.json({ error: 'Test code is required' }, { status: 400 });
        }

        const newTest = {
            id: `test-${Date.now()}`,
            name,
            code: code.toUpperCase(), // Ensure uppercase
            loincCode: loincCode || null,
            snomedCode: snomedCode || null,
            units: units || '',
            referenceRange: structuredRange,
            tatHours: Number(tatHours) || 24,
            department: department || 'General',
            specimenTypes: specimenTypes || ['Whole Blood', 'Serum'],
            methodology: methodology || '',
            price: Number(price) || 0,
            active: true,
            createdAt: new Date().toISOString(),
            createdBy: currentUser.username
        };

        dbData.testDefinitions.push(newTest);

        // Audit Log
        await logAudit(dbData, 'TestDefinition', newTest.id, 'CREATE', null, newTest, currentUser.username);

        await writeDb(dbData);

        return NextResponse.json(newTest, { status: 201 });

    } catch (error) {
        console.error('Test definition error:', error);
        return NextResponse.json({ error: 'Failed to create test definition' }, { status: 500 });
    }
}

// PUT: Update test definition
export async function PUT(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized - Please log in' }, { status: 401 });

    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden: Admin/Manager only' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { id, ...updates } = body;

        const dbData = await readDb();
        const index = dbData.testDefinitions.findIndex((t: any) => t.id === id);

        if (index === -1) {
            return NextResponse.json({ error: 'Test not found' }, { status: 404 });
        }

        const oldValue = { ...dbData.testDefinitions[index] };

        if (updates.hasOwnProperty('code') && !updates.code) {
            return NextResponse.json({ error: 'Test code cannot be empty' }, { status: 400 });
        }

        // Handle reference range update
        if (updates.referenceRange && typeof updates.referenceRange === 'string') {
            const match = updates.referenceRange.match(/(\d+\.?\d*)\s*-\s*(\d+\.?\d*)/);
            if (match) {
                updates.referenceRange = {
                    min: parseFloat(match[1]),
                    max: parseFloat(match[2]),
                    panicLow: oldValue.referenceRange?.panicLow ?? null,
                    panicHigh: oldValue.referenceRange?.panicHigh ?? null,
                    unit: updates.units || oldValue.units || '',
                    text: updates.referenceRange
                };
            }
        }

        dbData.testDefinitions[index] = { ...oldValue, ...updates, updatedAt: new Date().toISOString() };

        // Audit Log
        await logAudit(dbData, 'TestDefinition', id, 'UPDATE', oldValue, dbData.testDefinitions[index], currentUser.username);

        await writeDb(dbData);

        return NextResponse.json(dbData.testDefinitions[index]);

    } catch (error) {
        return NextResponse.json({ error: 'Failed to update test definition' }, { status: 500 });
    }
}

// DELETE: Soft delete test definition
export async function DELETE(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized - Please log in' }, { status: 401 });

    if (currentUser.role !== 'admin') {
        return NextResponse.json({ error: 'Forbidden: Admin only' }, { status: 403 });
    }

    try {
        const { searchParams } = new URL(request.url);
        const id = searchParams.get('id');

        if (!id) {
            return NextResponse.json({ error: 'Missing test ID' }, { status: 400 });
        }

        const dbData = await readDb();
        const index = dbData.testDefinitions.findIndex((t: any) => t.id === id);

        if (index === -1) {
            return NextResponse.json({ error: 'Test not found' }, { status: 404 });
        }

        const oldValue = { ...dbData.testDefinitions[index] };

        // Soft delete - mark as inactive
        (dbData.testDefinitions[index] as any).active = false;
        (dbData.testDefinitions[index] as any).deletedAt = new Date().toISOString();
        (dbData.testDefinitions[index] as any).deletedBy = currentUser.username;

        // Audit Log
        await logAudit(dbData, 'TestDefinition', id, 'DELETE', oldValue, null, currentUser.username);

        await writeDb(dbData);

        return NextResponse.json({ success: true });

    } catch (error) {
        return NextResponse.json({ error: 'Failed to delete test definition' }, { status: 500 });
    }
}
