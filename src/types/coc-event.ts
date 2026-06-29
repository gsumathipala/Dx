/**
 * Chain of Custody (CoC) Event Types and Interfaces
 * Provides complete, auditable tracking of sample lifecycle
 */

export type CoCEventType =
    | 'COLLECTED'
    | 'RECEIVED'
    | 'TRANSFERRED'
    | 'TESTED'
    | 'STORED'
    | 'ALIQUOTED'
    | 'DISPOSED';

export interface CoCEvent {
    id: string;
    sampleId: string;
    accessionNumber: string;
    eventType: CoCEventType;
    timestamp: string; // ISO 8601 format
    performedBy: string; // User ID or username
    performedByName: string; // Full name for display
    location?: string; // Physical location or workstation
    fromLocation?: string; // For TRANSFERRED events
    toLocation?: string; // For TRANSFERRED events
    notes?: string; // Additional context
    signature?: string; // Digital signature hash
    metadata?: Record<string, any>; // Flexible data for specific event types
}

export interface CoCEventCreate {
    sampleId: string;
    accessionNumber: string;
    eventType: CoCEventType;
    performedBy: string;
    performedByName: string;
    location?: string;
    fromLocation?: string;
    toLocation?: string;
    notes?: string;
    metadata?: Record<string, any>;
}

export interface CoCTimeline {
    sampleId: string;
    accessionNumber: string;
    events: CoCEvent[];
    currentLocation?: string;
    currentStatus: string;
}

/**
 * Get display-friendly event type label
 */
export function getCoCEventLabel(eventType: CoCEventType): string {
    const labels: Record<CoCEventType, string> = {
        COLLECTED: 'Sample Collected',
        RECEIVED: 'Received in Lab',
        TRANSFERRED: 'Transferred',
        TESTED: 'Testing Performed',
        STORED: 'Stored',
        ALIQUOTED: 'Aliquot Created',
        DISPOSED: 'Disposed'
    };
    return labels[eventType];
}

/**
 * Get color code for event type (for UI display)
 */
export function getCoCEventColor(eventType: CoCEventType): string {
    const colors: Record<CoCEventType, string> = {
        COLLECTED: 'blue',
        RECEIVED: 'green',
        TRANSFERRED: 'purple',
        TESTED: 'orange',
        STORED: 'gray',
        ALIQUOTED: 'cyan',
        DISPOSED: 'red'
    };
    return colors[eventType];
}
