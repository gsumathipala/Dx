import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';
import { db } from '@/db';
import { sessions, users } from '@/db/schema';
import { eq } from 'drizzle-orm';
import bcrypt from 'bcryptjs';

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

const DEFAULT_DEPARTMENTS = [
    { name: 'Clinical Biochemistry', code: 'CHEM', type: 'clinical', description: 'Routine chemistry, enzymes, metabolic panels.' },
    { name: 'Hematology', code: 'HEM', type: 'clinical', description: 'Blood counts (CBC), coagulation, films.' },
    { name: 'Microbiology', code: 'MICRO', type: 'microbiology', description: 'Bacteriology, cultures, sensitivity testing.' },
    { name: 'Histopathology', code: 'HISTO', type: 'histopathology', description: 'Tissue biopsy processing and microscopic exam.' },
    { name: 'Immunology / Serology', code: 'IMM', type: 'clinical', description: 'Antibody testing, autoimmune, allergy.' },
    { name: 'Urinalysis', code: 'UA', type: 'clinical', description: 'Urine chemistry and microscopy.' },
    { name: 'Cytopathology', code: 'CYTO', type: 'histopathology', description: 'Pap smears, fine needle aspirations (FNA).' },
    { name: 'Blood Bank', code: 'BB', type: 'clinical', description: 'Transfusion medicine, typing, cross-match.' },
    { name: 'Molecular Diagnostics', code: 'MOL', type: 'clinical', description: 'PCR, genetic testing, viral loads.' },
    { name: 'Toxicology', code: 'TOX', type: 'clinical', description: 'Drug monitoring and abuse screening.' },
    { name: 'Phlebotomy', code: 'PHLEB', type: 'logistics', description: 'Specimen collection services.' },
    { name: 'Central Accessioning', code: 'ACC', type: 'logistics', description: 'Specimen reception, sorting, and labeling.' },
    { name: 'Point of Care (POCT)', code: 'POCT', type: 'logistics', description: 'Bedside testing management.' }
];

export async function GET(request: Request) {
    const authUser = await getAuthenticatedUser();
    if (!authUser) return NextResponse.json({ error: 'Unauthorized - Please log in' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const includeDisabled = searchParams.get('includeDisabled') === 'true';

    const db = await readDb();
    let modified = false;

    if (!db.departments) {
        db.departments = [];
        modified = true;
    }

    // Smart Seed: Add missing departments by Code
    DEFAULT_DEPARTMENTS.forEach(def => {
        if (!db.departments.find((d: any) => d.code === def.code)) {
            db.departments.push({
                id: uuidv4(),
                ...def,
                enabled: true, // Default to enabled
                createdAt: new Date().toISOString(),
                lastModifiedAt: null,
                lastModifiedBy: null
            });
            modified = true;
        }
    });

    if (modified) await writeDb(db);

    // Filter out disabled departments unless explicitly requested
    let departments = db.departments;
    if (!includeDisabled) {
        departments = departments.filter((d: any) => d.enabled !== false);
    }

    return NextResponse.json(departments);
}

export async function POST(request: Request) {
    try {
        const user = await getAuthenticatedUser();

        if (!user) {
            return NextResponse.json({ error: 'Unauthorized - Please log in' }, { status: 401 });
        }

        // RBAC: Admin only
        if (user.role !== 'admin') {
            return NextResponse.json({ error: `Forbidden - Admin role required (you have: ${user.role})` }, { status: 403 });
        }

        const body = await request.json();
        const dbData = await readDb();
        if (!dbData.departments) dbData.departments = [];

        // Duplicate Check
        if (dbData.departments.find((d: any) => d.code === body.code)) {
            return NextResponse.json({ error: 'Department code already exists' }, { status: 409 });
        }

        // Create New Department
        const newDept = {
            id: uuidv4(),
            name: body.name,
            code: body.code.toUpperCase(),
            type: body.type || 'clinical',
            description: body.description || null,
            enabled: true,
            createdAt: new Date().toISOString(),
            lastModifiedAt: null,
            lastModifiedBy: null
        };

        dbData.departments.push(newDept);
        await writeDb(dbData);

        return NextResponse.json({ success: true, department: newDept });
    } catch (error) {
        console.error('Error creating department:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

// Toggle Department Enabled/Disabled (Admin with Password)
export async function PUT(request: Request) {
    try {
        const user = await getAuthenticatedUser();

        if (!user) {
            return NextResponse.json({ error: 'Unauthorized - Please log in' }, { status: 401 });
        }

        // RBAC: Admin only
        if (user.role !== 'admin') {
            return NextResponse.json({ error: 'Forbidden - Admin only' }, { status: 403 });
        }

        const { departmentId, enabled, adminPassword } = await request.json();
        const dbData = await readDb();

        // Verify admin password against bcrypt hash
        const adminUser = dbData.users.find((u: any) => u.username === user.username);
        const passwordValid = adminUser && await bcrypt.compare(String(adminPassword), adminUser.password);
        if (!passwordValid) {
            return NextResponse.json({ error: 'Invalid admin password' }, { status: 401 });
        }

        // Find department
        const dept = dbData.departments?.find((d: any) => d.id === departmentId);
        if (!dept) {
            return NextResponse.json({ error: 'Department not found' }, { status: 404 });
        }

        // Toggle status
        dept.enabled = enabled;
        dept.lastModifiedAt = new Date().toISOString();
        dept.lastModifiedBy = user.username;

        // Audit log
        // Audit log
        await logAudit(dbData, 'Department', departmentId, enabled ? 'ENABLE_DEPARTMENT' : 'DISABLE_DEPARTMENT', null, dept, user.username);

        await writeDb(dbData);

        return NextResponse.json({ success: true, department: dept });
    } catch (error) {
        console.error('Error toggling department:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
