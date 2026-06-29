import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import { readDb, writeDb, logAudit, fuzzyMatch } from '@/lib/db';
import { cookies } from 'next/headers';
import { db } from '@/db';
import { sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { v4 as uuidv4 } from 'uuid';

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

// GET: Search Patients (with Fuzzy Search)
export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get('q')?.toLowerCase();

    const dbData = await readDb();
    let results = dbData.patients || [];

    if (query) {
        // Advanced Search Logic (Issue #11 Solved)
        results = results.filter((p: any) => {
            const fullName = (p.firstName + ' ' + p.lastName).toLowerCase();
            const id = p.id ? p.id.toLowerCase() : '';
            const mrn = p.mrn ? p.mrn.toLowerCase() : '';
            const dob = p.dob || '';

            // Exact/Partial Match
            if (id.includes(query) || mrn.includes(query) || dob.includes(query)) return true;
            if (fullName.includes(query)) return true;

            // Fuzzy Match for Typos
            if (fuzzyMatch(fullName, query)) return true;

            return false;
        });
    }

    return NextResponse.json(results.slice(0, 50));
}

// POST: Create New Patient
export async function POST(request: Request) {
    const currentUser = await getAuthenticatedUser();
    const username = currentUser?.username || 'system';

    try {
        const body = await request.json();
        const { firstName, lastName, dob, mrn, gender, phone, email, address } = body;

        const dbData = await readDb();

        // Check for duplicates (Issue #11/93)
        // Check by MRN or (Name + DOB)
        const existing = dbData.patients.find((p: any) =>
            (p.mrn === mrn) ||
            (p.firstName.toLowerCase() === firstName.toLowerCase() &&
                p.lastName.toLowerCase() === lastName.toLowerCase() &&
                p.dob === dob)
        );

        if (existing) {
            return NextResponse.json({ error: 'Patient already exists (Duplicate Check)' }, { status: 409 });
        }

        if (!mrn) {
            return NextResponse.json({ error: 'Hospital Number (MRN) is required' }, { status: 400 });
        }

        // Use UUID for internal ID, MRN for display/lookup
        // Or if schema forces ID, we use uuidv4()
        const newPatient = {
            id: uuidv4(),
            firstName,
            lastName,
            dob,
            gender: gender || 'Unknown',
            mrn,
            email: email || null,
            phone: phone || null,
            address: address || null,
        };

        dbData.patients.push(newPatient);

        await logAudit(dbData, 'Patient', newPatient.id, 'CREATE', null, newPatient, username);
        await writeDb(dbData);

        return NextResponse.json(newPatient, { status: 201 });
    } catch (error) {
        console.error('Create patient error:', error);
        return NextResponse.json({ error: 'Failed to create patient' }, { status: 500 });
    }
}

// PUT: Update Patient Details
export async function PUT(request: Request) {
    const currentUser = await getAuthenticatedUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const body = await request.json();
        const { id, updates } = body;

        if (!id) return NextResponse.json({ error: 'Patient ID required' }, { status: 400 });

        const dbData = await readDb();
        const index = dbData.patients.findIndex((p: any) => p.id === id);

        if (index === -1) {
            return NextResponse.json({ error: 'Patient not found' }, { status: 404 });
        }

        const oldPatient = { ...dbData.patients[index] };

        const newPatient = {
            ...oldPatient,
            ...updates,
        };

        dbData.patients[index] = newPatient;

        await logAudit(dbData, 'Patient', id, 'UPDATE', oldPatient, newPatient, currentUser.username);
        await writeDb(dbData);

        return NextResponse.json(newPatient);
    } catch (error) {
        return NextResponse.json({ error: 'Update failed' }, { status: 500 });
    }
}
