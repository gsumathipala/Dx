import type { Workstation, RoutingRule, RoutingAssignment } from '@/types/workstation';
import { canAcceptTest } from '@/types/workstation';

/**
 * Routing Engine for Automated Test Assignment
 * Implements rules-based logic to route tests to appropriate workstations
 */

export interface RoutingRequest {
    testId: string;
    sampleId: string;
    accessionNumber: string;
    sampleType: string;
    priority?: number; // 1 (STAT) to 10 (routine)
    requiredBy?: string; // ISO timestamp for TAT deadline
}

export interface RoutingResult {
    success: boolean;
    assignment?: RoutingAssignment;
    error?: string;
    reason?: string;
}

export class RoutingEngine {
    private workstations: Workstation[];
    private routingRules: RoutingRule[];

    constructor(workstations: Workstation[], routingRules: RoutingRule[]) {
        this.workstations = workstations;
        this.routingRules = routingRules;
    }

    /**
     * Route a single test to the best available workstation
     */
    public async routeTest(request: RoutingRequest): Promise<RoutingResult> {
        // Find routing rule for this test
        const rule = this.routingRules.find(r => r.testId === request.testId);

        if (!rule) {
            return {
                success: false,
                error: 'No routing rule defined for this test',
                reason: `Test ${request.testId} has no routing configuration`
            };
        }

        // Check sample type compatibility if specified
        if (rule.sampleType && rule.sampleType !== request.sampleType) {
            return {
                success: false,
                error: 'Sample type mismatch',
                reason: `Test requires ${rule.sampleType} but received ${request.sampleType}`
            };
        }

        // Get candidate workstations (in priority order)
        const candidates = this.getCandidateWorkstations(rule, request);

        if (candidates.length === 0) {
            return {
                success: false,
                error: 'No available workstations',
                reason: 'All suitable workstations are offline or at capacity'
            };
        }

        // Select best workstation using load balancing
        const selectedWorkstation = this.selectBestWorkstation(candidates, request);

        // Create assignment
        const assignment: RoutingAssignment = {
            testId: request.testId,
            sampleId: request.sampleId,
            accessionNumber: request.accessionNumber,
            workstationId: selectedWorkstation.id,
            workstationName: selectedWorkstation.name,
            assignedAt: new Date().toISOString(),
            priority: request.priority || rule.priority,
            estimatedCompletionTime: this.calculateETA(selectedWorkstation)
        };

        return {
            success: true,
            assignment
        };
    }

    /**
     * Route multiple tests (batch routing)
     */
    public async routeBatch(requests: RoutingRequest[]): Promise<RoutingResult[]> {
        return Promise.all(requests.map(req => this.routeTest(req)));
    }

    /**
     * Get candidate workstations for a test
     */
    private getCandidateWorkstations(rule: RoutingRule, request: RoutingRequest): Workstation[] {
        const candidates: Workstation[] = [];

        // Check each preferred workstation in order
        for (const workstationId of rule.workstationIds) {
            const workstation = this.workstations.find(w => w.id === workstationId);

            if (!workstation) continue;

            // Check if workstation can accept the test
            if (!canAcceptTest(workstation)) continue;

            // Check if workstation supports this test
            if (!workstation.supportedTests.includes(request.testId)) continue;

            // Check if workstation supports this sample type
            if (!workstation.supportedSampleTypes.includes(request.sampleType)) continue;

            candidates.push(workstation);
        }

        return candidates;
    }

    /**
     * Select the best workstation from candidates using load balancing
     */
    private selectBestWorkstation(
        candidates: Workstation[],
        request: RoutingRequest
    ): Workstation {
        // For STAT/urgent tests, prefer the workstation with lowest queue
        if (request.priority && request.priority <= 3) {
            return candidates.reduce((best, current) =>
                (current.queuedTests < best.queuedTests) ? current : best
            );
        }

        // For routine tests, use round-robin load balancing
        // Find workstation with lowest utilization
        return candidates.reduce((best, current) => {
            const currentUtil = current.currentTests / current.maxThroughput;
            const bestUtil = best.currentTests / best.maxThroughput;
            return currentUtil < bestUtil ? current : best;
        });
    }

    /**
     * Calculate estimated completion time
     */
    private calculateETA(workstation: Workstation): string {
        // Simple estimation: assume 30 minutes per test in queue
        const minutesPerTest = 30;
        const queueMinutes = workstation.queuedTests * minutesPerTest;

        const eta = new Date();
        eta.setMinutes(eta.getMinutes() + queueMinutes);

        return eta.toISOString();
    }

    /**
     * Re-route a test (e.g., if workstation goes offline)
     */
    public async rerouteTest(
        originalAssignment: RoutingAssignment,
        request: RoutingRequest
    ): Promise<RoutingResult> {
        // Exclude the original workstation from candidates
        const originalWorkstationId = originalAssignment.workstationId;

        // Temporarily mark original workstation as unavailable
        const originalWorkstation = this.workstations.find(w => w.id === originalWorkstationId);
        const originalStatus = originalWorkstation?.status;

        if (originalWorkstation) {
            originalWorkstation.status = 'Offline';
        }

        const result = await this.routeTest(request);

        // Restore original status
        if (originalWorkstation && originalStatus) {
            originalWorkstation.status = originalStatus;
        }

        return result;
    }
}

/**
 * Create a routing engine instance
 */
export async function createRoutingEngine(
    workstations: Workstation[],
    routingRules: RoutingRule[]
): Promise<RoutingEngine> {
    return new RoutingEngine(workstations, routingRules);
}
