import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import type { StorageLocation, StorageLocationCreate, StorageHierarchy, StorageTree } from '@/types/storage';
import { getAuthUser } from '@/lib/auth';

/**
 * GET /api/storage
 * Retrieve all storage locations or build hierarchical tree
 */
export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const hierarchical = searchParams.get('hierarchical') === 'true';
        const parentId = searchParams.get('parentId');

        const db = await readDb();
        const locations: StorageLocation[] = db.storageLocations || [];

        if (parentId) {
            // Get children of specific parent
            const children = locations.filter(l => l.parentId === parentId);
            return NextResponse.json(children);
        }

        if (hierarchical) {
            // Build hierarchical tree
            const tree = buildHierarchicalTree(locations);
            return NextResponse.json(tree);
        }

        // Return flat list
        return NextResponse.json(locations);
    } catch (error) {
        console.error('Storage GET error:', error);
        return NextResponse.json(
            { error: 'Failed to retrieve storage locations' },
            { status: 500 }
        );
    }
}

/**
 * POST /api/storage
 * Create new storage location
 */
export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager', 'scientist'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    try {
        const body: StorageLocationCreate = await request.json();

        // Validation
        if (!body.name || !body.type) {
            return NextResponse.json(
                { error: 'Missing required fields: name, type' },
                { status: 400 }
            );
        }

        const db = await readDb();
        if (!db.storageLocations) db.storageLocations = [];

        // Validate parent exists if parentId provided
        if (body.parentId) {
            const parentExists = db.storageLocations.some((l: StorageLocation) => l.id === body.parentId);
            if (!parentExists) {
                return NextResponse.json(
                    { error: 'Parent location not found' },
                    { status: 404 }
                );
            }
        }

        const newLocation: StorageLocation = {
            id: Date.now().toString(),
            name: body.name,
            type: body.type,
            parentId: body.parentId,
            temperature: body.temperature,
            temperatureUnit: body.temperatureUnit || 'C',
            capacity: body.capacity,
            currentCount: 0,
            notes: body.notes,
            status: 'Active',
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        db.storageLocations.push(newLocation);
        await writeDb(db);

        return NextResponse.json(newLocation, { status: 201 });
    } catch (error) {
        console.error('Storage POST error:', error);
        return NextResponse.json(
            { error: 'Failed to create storage location' },
            { status: 500 }
        );
    }
}

/**
 * PUT /api/storage
 * Update storage location
 */
export async function PUT(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager', 'scientist'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    try {
        const body = await request.json();
        const { id, ...updates } = body;

        if (!id) {
            return NextResponse.json({ error: 'Location ID required' }, { status: 400 });
        }

        const db = await readDb();
        if (!db.storageLocations) db.storageLocations = [];

        const locationIndex = db.storageLocations.findIndex((l: StorageLocation) => l.id === id);
        if (locationIndex === -1) {
            return NextResponse.json({ error: 'Location not found' }, { status: 404 });
        }

        db.storageLocations[locationIndex] = {
            ...db.storageLocations[locationIndex],
            ...updates,
            updatedAt: new Date().toISOString()
        };

        await writeDb(db);
        return NextResponse.json(db.storageLocations[locationIndex]);
    } catch (error) {
        console.error('Storage PUT error:', error);
        return NextResponse.json(
            { error: 'Failed to update storage location' },
            { status: 500 }
        );
    }
}

/**
 * DELETE /api/storage
 * Delete storage location (only if empty)
 */
export async function DELETE(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    try {
        const { searchParams } = new URL(request.url);
        const id = searchParams.get('id');

        if (!id) {
            return NextResponse.json({ error: 'Location ID required' }, { status: 400 });
        }

        const db = await readDb();
        if (!db.storageLocations) db.storageLocations = [];

        const location = db.storageLocations.find((l: StorageLocation) => l.id === id);
        if (!location) {
            return NextResponse.json({ error: 'Location not found' }, { status: 404 });
        }

        // Check if has children
        const hasChildren = db.storageLocations.some((l: StorageLocation) => l.parentId === id);
        if (hasChildren) {
            return NextResponse.json(
                { error: 'Cannot delete location with child locations' },
                { status: 400 }
            );
        }

        // Check if has samples
        if (location.currentCount && location.currentCount > 0) {
            return NextResponse.json(
                { error: 'Cannot delete location with samples' },
                { status: 400 }
            );
        }

        db.storageLocations = db.storageLocations.filter((l: StorageLocation) => l.id !== id);
        await writeDb(db);

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Storage DELETE error:', error);
        return NextResponse.json(
            { error: 'Failed to delete storage location' },
            { status: 500 }
        );
    }
}

/**
 * Build hierarchical tree structure from flat list of locations
 */
function buildHierarchicalTree(locations: StorageLocation[]): StorageTree {
    const hierarchyMap = new Map<string, StorageHierarchy>();

    // First pass: create hierarchy objects
    locations.forEach(location => {
        hierarchyMap.set(location.id, {
            location,
            children: [],
            path: [],
            level: 0
        });
    });

    // Second pass: build parent-child relationships
    const rootNodes: StorageHierarchy[] = [];

    locations.forEach(location => {
        const node = hierarchyMap.get(location.id)!;

        if (location.parentId) {
            const parent = hierarchyMap.get(location.parentId);
            if (parent) {
                parent.children.push(node);
                node.level = parent.level + 1;
                node.path = [...parent.path, location.name];
            }
        } else {
            rootNodes.push(node);
            node.path = [location.name];
        }
    });

    return {
        root: rootNodes,
        totalLocations: locations.length,
        totalSamples: locations.reduce((sum, l) => sum + (l.currentCount || 0), 0)
    };
}
