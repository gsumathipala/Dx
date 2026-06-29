/**
 * Hierarchical Storage Location Types
 * Support 4-level hierarchy: Equipment → Shelf → Rack → Box/Position
 */

export type StorageLocationType = 'Equipment' | 'Shelf' | 'Rack' | 'Box';

export interface StorageLocation {
    id: string;
    name: string;
    type: StorageLocationType;
    parentId?: string; // Reference to parent location
    temperature?: number; // In Celsius
    temperatureUnit?: string; // 'C' | 'F'
    capacity?: number; // Total positions/samples this can hold
    currentCount?: number; // Current number of samples stored
    notes?: string;
    status: 'Active' | 'Maintenance' | 'Decommissioned';
    createdAt: string;
    updatedAt: string;
}

export interface StorageLocationCreate {
    name: string;
    type: StorageLocationType;
    parentId?: string;
    temperature?: number;
    temperatureUnit?: string;
    capacity?: number;
    notes?: string;
}

export interface StorageHierarchy {
    location: StorageLocation;
    children: StorageHierarchy[];
    samples?: any[]; // Samples stored at this location
    path: string[]; // Full path from root to this location
    level: number; // 0 = Equipment, 1 = Shelf, 2 = Rack, 3 = Box
}

export interface StorageTree {
    root: StorageHierarchy[];
    totalLocations: number;
    totalSamples: number;
}

/**
 * Get full storage path as string
 * Example: "Freezer A > Shelf 2 > Rack B > Box 5"
 */
export function getStoragePathString(path: string[]): string {
    return path.join(' > ');
}

/**
 * Build hierarchical storage path from location ID
 */
export async function buildStoragePath(
    locationId: string,
    locations: StorageLocation[]
): Promise<string[]> {
    const path: string[] = [];
    let currentId: string | undefined = locationId;

    while (currentId) {
        const location = locations.find(l => l.id === currentId);
        if (!location) break;
        path.unshift(location.name);
        currentId = location.parentId;
    }

    return path;
}

/**
 * Check if storage location is at capacity
 */
export function isStorageAtCapacity(location: StorageLocation): boolean {
    if (!location.capacity) return false;
    return (location.currentCount || 0) >= location.capacity;
}

/**
 * Get storage utilization percentage
 */
export function getStorageUtilization(location: StorageLocation): number {
    if (!location.capacity || location.capacity === 0) return 0;
    return Math.round(((location.currentCount || 0) / location.capacity) * 100);
}

/**
 * Get color for utilization level
 */
export function getUtilizationColor(utilization: number): string {
    if (utilization >= 90) return 'red';
    if (utilization >= 75) return 'orange';
    if (utilization >= 50) return 'yellow';
    return 'green';
}
