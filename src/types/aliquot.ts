/**
 * Aliquot and Sample Derivative Types
 * Track parent-child relationships for samples
 */

export interface Aliquot {
    id: string;
    parentSampleId: string;
    parentAccessionNumber: string;
    aliquotNumber: string; // e.g., A1, A2, B1
    fullIdentifier: string; // e.g., ACC-20231216-0001-A1
    type: string; // Sample type (Serum, Plasma, etc.)
    volume?: number; // Volume in mL or µL
    volumeUnit?: string; // 'mL' | 'µL'
    containerId?: string; // Barcode/container ID
    location?: string; // Storage location
    createdAt: string; // ISO timestamp
    createdBy: string; // User ID
    createdByName: string; // Full name
    purpose?: string; // Why aliquot was created
    status: 'Active' | 'Used' | 'Disposed';
    usedAt?: string; // When aliquot was consumed
    disposedAt?: string; // When aliquot was disposed
}

export interface AliquotCreate {
    parentSampleId: string;
    parentAccessionNumber: string;
    type: string;
    volume?: number;
    volumeUnit?: string;
    containerId?: string;
    location?: string;
    createdBy: string;
    createdByName: string;
    purpose?: string;
    count?: number; // Number of aliquots to create (default: 1)
}

export interface SampleWithAliquots {
    id: string;
    accessionNumber: string;
    type: string;
    containerId?: string;
    location?: string;
    aliquots: Aliquot[];
    totalAliquots: number;
    activeAliquots: number;
}

/**
 * Generate aliquot identifier
 * Format: {accessionNumber}-{aliquotNumber}
 * Example: ACC-20231216-0001-A1
 */
export function generateAliquotIdentifier(
    accessionNumber: string,
    aliquotNumber: string
): string {
    return `${accessionNumber}-${aliquotNumber}`;
}

/**
 * Generate sequential aliquot numbers
 * A1, A2, ..., A9, B1, B2, etc.
 */
export function generateAliquotNumber(index: number): string {
    const letter = String.fromCharCode(65 + Math.floor(index / 9)); // A, B, C, ...
    const number = (index % 9) + 1; // 1-9
    return `${letter}${number}`;
}
