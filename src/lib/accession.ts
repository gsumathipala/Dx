import { client } from '@/db';

/**
 * Generates the next sequential accession number for the current day.
 * Format: YYYY-MM-DD-XXXX (e.g., 2025-12-22-0001)
 *
 * Uses a synchronous better-sqlite3 transaction so concurrent calls within the
 * same process serialize correctly. The `unique` constraint on accession_number
 * acts as a final safety net against any cross-process duplicates.
 */
export function generateNextAccessionNumber(): string {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    const prefix = `${year}-${month}-${day}`;

    const getNext = client.transaction(() => {
        const row = client.prepare(
            `SELECT accession_number FROM orders WHERE accession_number LIKE ? ORDER BY accession_number DESC LIMIT 1`
        ).get(`${prefix}-%`) as { accession_number: string } | undefined;

        let nextSequence = 1;
        if (row) {
            const parts = row.accession_number.split('-');
            if (parts.length === 4) {
                const lastSeq = parseInt(parts[3], 10);
                if (!isNaN(lastSeq)) nextSequence = lastSeq + 1;
            }
        }
        return `${prefix}-${String(nextSequence).padStart(4, '0')}`;
    });

    return getNext();
}
