
export interface LabResult {
    accessionNumber: string;
    testCode: string;
    value: string;
    units: string;
    flags: string;
    timestamp: string;
}

export function parseHL7(raw: string): LabResult[] {
    const segments = raw.split('\r');
    let accessionNumber = '';
    const results: LabResult[] = [];
    const timestamp = new Date().toISOString();

    for (const segment of segments) {
        const fields = segment.split('|');
        const segmentType = fields[0];

        if (segmentType === 'OBR') {
            // OBR-3 is usually Caller Accession / Filler Order Number
            // OBR|1|Order123|Accession456|...
            accessionNumber = fields[3] || fields[2];
        } else if (segmentType === 'OBX') {
            // OBX|1|NM|GLU^Glucose||105|mg/dL|70-100|H|||F
            // 3: ID, 5: Value, 6: Units, 8: Flag
            const testIdField = fields[3] || '';
            const testCode = testIdField.split('^')[0]; // GLU
            const value = fields[5];
            const units = fields[6];
            const flags = fields[8] || 'N';

            if (accessionNumber && testCode && value) {
                results.push({
                    accessionNumber,
                    testCode,
                    value,
                    units,
                    flags,
                    timestamp
                });
            }
        }
    }
    return results;
}
