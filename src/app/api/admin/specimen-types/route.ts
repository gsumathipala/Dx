import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { cookies } from 'next/headers';

export async function GET() {
    const db = await readDb();
    return NextResponse.json(db.specimenTypes || []);
}

export async function POST(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    // RBAC: Admin or Manager
    const currentUser = JSON.parse(session.value);
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { type } = await request.json();
        const db = await readDb();

        if (db.specimenTypes.includes(type)) {
            return NextResponse.json({ error: 'Specimen type already exists' }, { status: 409 });
        }

        db.specimenTypes.push(type);
        await logAudit(db, 'SpecimenType', type, 'CREATE', null, type, currentUser.username);
        await writeDb(db);

        return NextResponse.json(db.specimenTypes);
    } catch (e) {
        return NextResponse.json({ error: 'Failed to add type' }, { status: 500 });
    }
}

// RENAME (PUT)
export async function PUT(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const currentUser = JSON.parse(session.value);
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { oldType, newType } = await request.json();
        const db = await readDb();

        if (!db.specimenTypes.includes(oldType)) {
            return NextResponse.json({ error: 'Old type not found' }, { status: 404 });
        }
        if (db.specimenTypes.includes(newType)) {
            return NextResponse.json({ error: 'New type name already exists' }, { status: 409 });
        }

        // 1. Update the master list
        const idx = db.specimenTypes.indexOf(oldType);
        db.specimenTypes[idx] = newType;

        // 2. Cascade Rename: Update Test Definitions
        let updatedCount = 0;
        db.testDefinitions.forEach((test: any) => {
            if (test.specimenTypes && test.specimenTypes.includes(oldType)) {
                // Replace oldType with newType in the array
                test.specimenTypes = test.specimenTypes.map((t: string) => t === oldType ? newType : t);
                updatedCount++;
            }
        });

        // 3. Cascade Rename: Update Active Specimens? (Optional, but good for consistency)
        // Usually specimen.type is a string.
        db.specimens?.forEach((spec: any) => {
            if (spec.type === oldType) spec.type = newType;
        });

        await logAudit(db, 'SpecimenType', oldType, 'RENAME', oldType, newType, currentUser.username);
        await writeDb(db);

        return NextResponse.json({ success: true, message: `Renamed to ${newType}. Cached references updated.` });

    } catch (e) {
        return NextResponse.json({ error: 'Failed to rename' }, { status: 500 });
    }
}

// DELETE
export async function DELETE(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const currentUser = JSON.parse(session.value);
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { searchParams } = new URL(request.url);
        const typeToDelete = searchParams.get('type');
        const force = searchParams.get('force') === 'true'; // Allow bypass if user insists

        const db = await readDb();

        if (!typeToDelete) {
            return NextResponse.json({ error: 'Missing type parameter' }, { status: 400 });
        }

        if (!db.specimenTypes.includes(typeToDelete)) {
            return NextResponse.json({ error: 'Type not found' }, { status: 404 });
        }

        // Usage Check
        const usedInTests = db.testDefinitions.filter((t: any) => t.specimenTypes?.includes(typeToDelete));
        const usedInSpecimens = db.specimens?.filter((s: any) => s.type === typeToDelete);

        if ((usedInTests.length > 0 || (usedInSpecimens && usedInSpecimens.length > 0)) && !force) {
            return NextResponse.json({
                error: 'USAGE_DETECTED',
                message: `Cannot delete '${typeToDelete}'. It is used in ${usedInTests.length} tests and ${usedInSpecimens?.length || 0} active specimens.`,
                usedInTests: usedInTests.map((t: any) => t.name)
            }, { status: 409 });
        }

        // Perform Delete
        db.specimenTypes = db.specimenTypes.filter((t: string) => t !== typeToDelete);

        // Audit
        await logAudit(db, 'SpecimenType', typeToDelete, 'DELETE', typeToDelete, null, currentUser.username);
        await writeDb(db);

        return NextResponse.json({ success: true });

    } catch (e) {
        return NextResponse.json({ error: 'Failed to delete' }, { status: 500 });
    }
}
