import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import type { Workstation, RoutingRule, RoutingAssignment } from '@/types/workstation';
import { createRoutingEngine, type RoutingRequest } from '@/lib/routing-engine';
import { getAuthUser } from '@/lib/auth';

/**
 * POST /api/routing/assign
 * Automatically route tests to workstations
 */
export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const { tests, batch = false } = body; // tests can be single or array

        const db = await readDb();
        const workstations: Workstation[] = db.workstations || [];
        const routingRules: RoutingRule[] = db.routingRules || [];

        if (workstations.length === 0) {
            return NextResponse.json(
                { error: 'No workstations configured' },
                { status: 400 }
            );
        }

        // Create routing engine
        const engine = await createRoutingEngine(workstations, routingRules);

        let results;
        if (batch && Array.isArray(tests)) {
            // Batch routing
            results = await engine.routeBatch(tests);
        } else {
            // Single test routing
            const testRequest: RoutingRequest = Array.isArray(tests) ? tests[0] : tests;
            results = await engine.routeTest(testRequest);
        }

        // Store assignments if successful
        if (!db.routingAssignments) db.routingAssignments = [];

        if (Array.isArray(results)) {
            results.forEach(result => {
                if (result.success && result.assignment) {
                    db.routingAssignments.push(result.assignment);

                    // Update workstation queue
                    const workstation = workstations.find(w => w.id === result.assignment!.workstationId);
                    if (workstation) {
                        workstation.queuedTests = (workstation.queuedTests || 0) + 1;
                    }
                }
            });
        } else if (results.success && results.assignment) {
            db.routingAssignments.push(results.assignment);

            // Update workstation queue
            const workstation = workstations.find(w => w.id === results.assignment!.workstationId);
            if (workstation) {
                workstation.queuedTests = (workstation.queuedTests || 0) + 1;
            }
        }

        // Save updated workstation queues
        await writeDb(db);

        return NextResponse.json(results);
    } catch (error) {
        console.error('Routing POST error:', error);
        return NextResponse.json(
            { error: 'Failed to route tests' },
            { status: 500 }
        );
    }
}

/**
 * GET /api/routing/assignments
 * Retrieve routing assignments
 */
export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const workstationId = searchParams.get('workstationId');
        const accessionNumber = searchParams.get('accessionNumber');

        const db = await readDb();
        let assignments: RoutingAssignment[] = db.routingAssignments || [];

        if (workstationId) {
            assignments = assignments.filter(a => a.workstationId === workstationId);
        }
        if (accessionNumber) {
            assignments = assignments.filter(a => a.accessionNumber === accessionNumber);
        }

        return NextResponse.json(assignments);
    } catch (error) {
        console.error('Routing GET error:', error);
        return NextResponse.json(
            { error: 'Failed to retrieve assignments' },
            { status: 500 }
        );
    }
}
