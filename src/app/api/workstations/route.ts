import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import type { Workstation, WorkstationCreate, RoutingRule } from '@/types/workstation';
import { getAuthUser } from '@/lib/auth';

/**
 * GET /api/workstations
 * Retrieve all workstations or filter by status/department
 */
export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const status = searchParams.get('status');
        const department = searchParams.get('department');
        const includeRules = searchParams.get('includeRules') === 'true';

        const db = await readDb();
        let workstations: Workstation[] = db.workstations || [];

        // Apply filters
        if (status) {
            workstations = workstations.filter(w => w.status === status);
        }
        if (department) {
            workstations = workstations.filter(w => w.department === department);
        }

        if (includeRules) {
            const routingRules: RoutingRule[] = db.routingRules || [];
            return NextResponse.json({ workstations, routingRules });
        }

        return NextResponse.json(workstations);
    } catch (error) {
        console.error('Workstations GET error:', error);
        return NextResponse.json(
            { error: 'Failed to retrieve workstations' },
            { status: 500 }
        );
    }
}

/**
 * POST /api/workstations
 * Create new workstation
 */
export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    try {
        const body: WorkstationCreate = await request.json();

        // Validation
        if (!body.name || !body.type || !body.department) {
            return NextResponse.json(
                { error: 'Missing required fields: name, type, department' },
                { status: 400 }
            );
        }

        const db = await readDb();
        if (!db.workstations) db.workstations = [];

        const newWorkstation: Workstation = {
            id: Date.now().toString(),
            name: body.name,
            type: body.type,
            department: body.department,
            status: 'Online',
            supportedTests: body.supportedTests || [],
            supportedSampleTypes: body.supportedSampleTypes || [],
            maxThroughput: body.maxThroughput || 10,
            currentTests: 0,
            queuedTests: 0,
            connectionType: body.connectionType,
            ipAddress: body.ipAddress,
            port: body.port,
            manufacturer: body.manufacturer,
            model: body.model,
            serialNumber: body.serialNumber,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        db.workstations.push(newWorkstation);
        await writeDb(db);

        return NextResponse.json(newWorkstation, { status: 201 });
    } catch (error) {
        console.error('Workstations POST error:', error);
        return NextResponse.json(
            { error: 'Failed to create workstation' },
            { status: 500 }
        );
    }
}

/**
 * PUT /api/workstations
 * Update workstation (status, workload, etc.)
 */
export async function PUT(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const { id, ...updates } = body;

        if (!id) {
            return NextResponse.json({ error: 'Workstation ID required' }, { status: 400 });
        }

        const db = await readDb();
        if (!db.workstations) db.workstations = [];

        const workstationIndex = db.workstations.findIndex((w: Workstation) => w.id === id);
        if (workstationIndex === -1) {
            return NextResponse.json({ error: 'Workstation not found' }, { status: 404 });
        }

        db.workstations[workstationIndex] = {
            ...db.workstations[workstationIndex],
            ...updates,
            updatedAt: new Date().toISOString()
        };

        await writeDb(db);
        return NextResponse.json(db.workstations[workstationIndex]);
    } catch (error) {
        console.error('Workstations PUT error:', error);
        return NextResponse.json(
            { error: 'Failed to update workstation' },
            { status: 500 }
        );
    }
}

/**
 * DELETE /api/workstations
 * Delete workstation
 */
export async function DELETE(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    try {
        const { searchParams } = new URL(request.url);
        const id = searchParams.get('id');

        if (!id) {
            return NextResponse.json({ error: 'Workstation ID required' }, { status: 400 });
        }

        const db = await readDb();
        if (!db.workstations) db.workstations = [];

        const initialLength = db.workstations.length;
        db.workstations = db.workstations.filter((w: Workstation) => w.id !== id);

        if (db.workstations.length === initialLength) {
            return NextResponse.json({ error: 'Workstation not found' }, { status: 404 });
        }

        await writeDb(db);
        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Workstations DELETE error:', error);
        return NextResponse.json(
            { error: 'Failed to delete workstation' },
            { status: 500 }
        );
    }
}
