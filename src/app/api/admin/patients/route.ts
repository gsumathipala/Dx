import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { cookies } from 'next/headers';

// GET: Search Patients
export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get('q');

    // Auth Check
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const currentUser = JSON.parse(session.value);

    // Only Admin or Manager (if needed) can access this full management list, keeping consistent with "Admin cannot edit"
    if (currentUser.role !== 'admin' && currentUser.role !== 'manager') {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    const db = await readDb();
    const patients = db.patients || [];

    if (query) {
        const q = query.toLowerCase();
        const results = patients.filter((p: any) => {
            const fullName = `${p.firstName || ''} ${p.lastName || ''}`.toLowerCase();
            return fullName.includes(q) ||
                (p.mrn && p.mrn.toLowerCase().includes(q)) ||
                (p.email && p.email.toLowerCase().includes(q));
        }).slice(0, 50);
        return NextResponse.json(results);
    }

    return NextResponse.json(patients.slice(0, 50)); // Default Limit
}

// PUT: Update Patient
export async function PUT(request: Request) {
    // Auth Check
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const currentUser = JSON.parse(session.value);

    // Strict Admin check as per request "Admin cannot edit..."
    if (currentUser.role !== 'admin') {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { id, updates } = body;

        const db = await readDb();
        if (!db.patients) db.patients = [];

        const idx = db.patients.findIndex((p: any) => p.id === id);
        if (idx === -1) return NextResponse.json({ error: 'Patient not found' }, { status: 404 });

        // Merge updates
        db.patients[idx] = { ...db.patients[idx], ...updates };
        await writeDb(db);

        return NextResponse.json({ message: 'Patient updated', patient: db.patients[idx] });

    } catch (e) {
        return NextResponse.json({ error: 'Update failed' }, { status: 500 });
    }
}
