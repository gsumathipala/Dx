import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { v4 as uuidv4 } from 'uuid';
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

export async function GET(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const type = searchParams.get('type');
    const dbData = await readDb();

    if (type === 'materials') {
        const materials = dbData.qcMaterials || [];
        const definitions = dbData.qcDefinitions || [];

        // Return hierarchy
        const fullData = materials.map((mat: any) => ({
            ...mat,
            analytes: definitions.filter((d: any) => d.materialId === mat.id)
        }));
        return NextResponse.json(fullData);
    }
    else if (type === 'definitions') {
        return NextResponse.json(dbData.qcDefinitions || []);
    }
    else if (type === 'runs') {
        const defId = searchParams.get('defId');
        let runs = dbData.qcRuns || [];
        if (defId) {
            runs = runs.filter((r: any) => r.qcDefId === defId);
        }
        // Return last 100 runs sorted by date desc
        runs.sort((a: any, b: any) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
        return NextResponse.json(runs.slice(0, 100));
    }

    return NextResponse.json({ error: 'Invalid type' }, { status: 400 });
}

export async function POST(request: Request) {
    // Require authentication for POST operations
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const body = await request.json();
        const { type, data } = body;
        const dbData = await readDb();

        if (type === 'seed') {
            // === SEED STANDARD CONTROLS ===
            dbData.qcMaterials = [];
            dbData.qcDefinitions = [];
            dbData.qcRuns = []; // Reset runs for clean slate

            // 1. Hematology Controls (Tri-Level)
            const hemeLevels = [
                { name: 'Heme Control Low', level: 'Level 1', wbc: 2.5, hgb: 6.0, plt: 60 },
                { name: 'Heme Control Normal', level: 'Level 2', wbc: 7.8, hgb: 13.8, plt: 245 },
                { name: 'Heme Control High', level: 'Level 3', wbc: 22.0, hgb: 19.5, plt: 550 }
            ];

            for (const lvl of hemeLevels) {
                const matId = uuidv4();
                dbData.qcMaterials.push({
                    id: matId,
                    name: lvl.name,
                    lot: `LOT-H${Math.floor(Math.random() * 900) + 100}`,
                    expiration: '2026-12-31',
                    department: 'Hematology'
                });

                dbData.qcDefinitions.push(
                    { id: uuidv4(), materialId: matId, testCode: 'WBC', testName: 'White Blood Cells', mean: lvl.wbc, sd: lvl.wbc * 0.05, unit: 'K/uL' },
                    { id: uuidv4(), materialId: matId, testCode: 'HGB', testName: 'Hemoglobin', mean: lvl.hgb, sd: lvl.hgb * 0.03, unit: 'g/dL' },
                    { id: uuidv4(), materialId: matId, testCode: 'PLT', testName: 'Platelets', mean: lvl.plt, sd: lvl.plt * 0.1, unit: 'K/uL' }
                );
            }

            // 2. Chemistry Controls (Bi-Level)
            const chemLevels = [
                { name: 'Chem Control Normal', level: 'Level 1', glu: 92, na: 141, k: 4.1 },
                { name: 'Chem Control Path', level: 'Level 2', glu: 265, na: 158, k: 6.8 }
            ];

            for (const lvl of chemLevels) {
                const matId = uuidv4();
                dbData.qcMaterials.push({
                    id: matId,
                    name: lvl.name,
                    lot: `LOT-C${Math.floor(Math.random() * 900) + 100}`,
                    expiration: '2026-06-30',
                    department: 'Chemistry'
                });

                dbData.qcDefinitions.push(
                    { id: uuidv4(), materialId: matId, testCode: 'GLU', testName: 'Glucose', mean: lvl.glu, sd: lvl.glu * 0.04, unit: 'mg/dL' },
                    { id: uuidv4(), materialId: matId, testCode: 'NA', testName: 'Sodium', mean: lvl.na, sd: 1.5, unit: 'mmol/L' },
                    { id: uuidv4(), materialId: matId, testCode: 'K', testName: 'Potassium', mean: lvl.k, sd: 0.1, unit: 'mmol/L' }
                );
            }

            await writeDb(dbData);
            return NextResponse.json({ success: true, message: 'QC Database Seeded Successfully' });
        }
        else if (type === 'run') {
            if (!dbData.qcRuns) dbData.qcRuns = [];
            const newRun = {
                ...data,
                id: uuidv4(),
                timestamp: new Date().toISOString()
            };
            dbData.qcRuns.push(newRun);
            await writeDb(dbData);
            return NextResponse.json(newRun);
        }
        else if (type === 'update_definition') {
            // EDIT THRESHOLDS
            const { id, mean, sd } = data;
            const idx = dbData.qcDefinitions.findIndex((d: any) => d.id === id);
            if (idx >= 0) {
                dbData.qcDefinitions[idx].mean = parseFloat(mean);
                dbData.qcDefinitions[idx].sd = parseFloat(sd);
                await writeDb(dbData);
                return NextResponse.json({ success: true });
            }
            return NextResponse.json({ error: 'Definition not found' }, { status: 404 });
        }
        else if (type === 'create_material') {
            if (!dbData.qcMaterials) dbData.qcMaterials = [];
            const newMat = { ...data, id: uuidv4(), active: true };
            dbData.qcMaterials.push(newMat);
            await writeDb(dbData);
            return NextResponse.json(newMat);
        }
        else if (type === 'create_definition') {
            if (!dbData.qcDefinitions) dbData.qcDefinitions = [];
            const newDef = { ...data, id: uuidv4() };
            dbData.qcDefinitions.push(newDef);
            await writeDb(dbData);
            return NextResponse.json(newDef);
        }
        else if (type === 'delete_material') {
            const { id } = data;
            if (dbData.qcMaterials) {
                dbData.qcMaterials = dbData.qcMaterials.filter((m: any) => m.id !== id);
                // Cascade delete definitions
                if (dbData.qcDefinitions) {
                    dbData.qcDefinitions = dbData.qcDefinitions.filter((d: any) => d.materialId !== id);
                }
                await writeDb(dbData);
            }
            return NextResponse.json({ success: true });
        }
        else if (type === 'delete_definition') {
            const { id } = data;
            if (dbData.qcDefinitions) {
                dbData.qcDefinitions = dbData.qcDefinitions.filter((d: any) => d.id !== id);
                await writeDb(dbData);
            }
            return NextResponse.json({ success: true });
        }
        else if (type === 'update_material') {
            const { id, name, lot, department } = data;
            const idx = dbData.qcMaterials?.findIndex((m: any) => m.id === id);
            if (idx !== undefined && idx !== -1) {
                dbData.qcMaterials[idx] = { ...dbData.qcMaterials[idx], name, lot, department };
                await writeDb(dbData);
                return NextResponse.json(dbData.qcMaterials[idx]);
            }
            return NextResponse.json({ error: 'Material not found' }, { status: 404 });
        }

        return NextResponse.json({ error: 'Invalid type' }, { status: 400 });
    } catch (error) {
        console.error(error);
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}
