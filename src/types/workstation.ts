/**
 * Workstation and Instrument Types
 * Support automated test routing and workload management
 */

export type WorkstationStatus = 'Online' | 'Offline' | 'Maintenance' | 'Busy';

export interface Workstation {
    id: string;
    name: string;
    type: 'Analyzer' | 'Manual' | 'Microscopy' | 'Molecular' | 'Microbiology';
    department: string;
    status: WorkstationStatus;

    // Capabilities
    supportedTests: string[]; // Test IDs this workstation can perform
    supportedSampleTypes: string[]; // Sample types it accepts
    maxThroughput: number; // Tests per hour

    // Current workload
    currentTests: number; // Tests currently running
    queuedTests: number; // Tests in queue

    // Connection info
    connectionType?: 'ASTM' | 'HL7' | 'TCP/IP' | 'Serial' | 'Manual';
    ipAddress?: string;
    port?: number;

    // Metadata
    manufacturer?: string;
    model?: string;
    serialNumber?: string;
    lastMaintenanceDate?: string;
    nextMaintenanceDate?: string;

    createdAt: string;
    updatedAt: string;
}

export interface WorkstationCreate {
    name: string;
    type: Workstation['type'];
    department: string;
    supportedTests: string[];
    supportedSampleTypes: string[];
    maxThroughput?: number;
    connectionType?: Workstation['connectionType'];
    ipAddress?: string;
    port?: number;
    manufacturer?: string;
    model?: string;
    serialNumber?: string;
}

export interface RoutingRule {
    id: string;
    testId: string;
    testName: string;
    priority: number; // 1 (highest) to 10 (lowest)
    workstationIds: string[]; // Ordered list of preferred workstations
    sampleType?: string; // If specific sample type required
    conditions?: Record<string, any>; // Additional routing conditions
    createdAt: string;
    updatedAt: string;
}

export interface RoutingAssignment {
    testId: string;
    sampleId: string;
    accessionNumber: string;
    workstationId: string;
    workstationName: string;
    assignedAt: string;
    priority: number;
    estimatedCompletionTime?: string;
}

/**
 * Get workstation status color for UI
 */
export function getWorkstationStatusColor(status: WorkstationStatus): string {
    const colors: Record<WorkstationStatus, string> = {
        Online: 'green',
        Offline: 'red',
        Maintenance: 'orange',
        Busy: 'yellow'
    };
    return colors[status];
}

/**
 * Calculate workstation utilization percentage
 */
export function getWorkstationUtilization(workstation: Workstation): number {
    if (workstation.maxThroughput === 0) return 0;
    return Math.round((workstation.currentTests / workstation.maxThroughput) * 100);
}

/**
 * Check if workstation can accept more tests
 */
export function canAcceptTest(workstation: Workstation): boolean {
    if (workstation.status !== 'Online') return false;
    return workstation.currentTests < workstation.maxThroughput;
}
