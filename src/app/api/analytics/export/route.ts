import { NextResponse } from 'next/server';
import { db } from '@/db';
import { results, orders, patients, testDefinitions } from '@/db/schema';
import { eq, and, gte, lte, like } from 'drizzle-orm';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    const { searchParams } = new URL(request.url);
    const startDate = searchParams.get('startDate');
    const endDate = searchParams.get('endDate');
    const disease = searchParams.get('disease'); // e.g. "HIV", "COVID"

    try {
        // Build the query
        // We need to join Results -> Orders -> Patients
        // And optionally filter by Test Name (via TestDefinitions or just TestCode if we knew it)
        // Since we don't have direct joins in Drizzle SQLite easily without 'leftJoin' mapping manually in some versions,
        // we will select everything and filter or use the fluent join syntax if available.
        // Better-sqlite3 Drizzle supports joins.

        const query = db.select({
            patientId: patients.mrn, // Use MRN as ID for report
            gender: patients.gender,
            dob: patients.dob,
            address: patients.address, // Region proxy
            testName: testDefinitions.name,
            result: results.values,
            flags: results.resultFlags,
            date: results.timestamp,
        })
            .from(results)
            .leftJoin(orders, eq(results.orderId, orders.id))
            .leftJoin(patients, eq(orders.patientId, patients.id))
            .leftJoin(testDefinitions, eq(results.testId, testDefinitions.id));

        // Apply filters
        // Note: Drizzle's dynamic query building requires building an array of WHERE clauses
        const conditions = [];

        if (startDate) conditions.push(gte(results.timestamp, startDate));
        if (endDate) conditions.push(lte(results.timestamp, endDate));

        // Filter by Disease Name (fuzzy match on Test Name)
        if (disease && disease !== 'All') {
            conditions.push(like(testDefinitions.name, `%${disease}%`));
        }

        // Only "Final" or "Validated" results? strictly speaking yes, but for now take all

        // Apply Where
        let finalQuery: any = query;
        if (conditions.length > 0) {
            finalQuery = query.where(and(...conditions));
        }

        const data = await finalQuery;

        // Convert to CSV
        const csvHeader = 'PatientID,Gender,DOB,District,Test,Result,Flags,Date\n';
        const csvRows = data.map((row: any) => {
            // Parse JSON result values to string if needed, or just dump it
            let resultStr = row.result;
            if (typeof row.result === 'string' && (row.result.startsWith('{') || row.result.startsWith('['))) {
                try {
                    // Try to extract a meaningful value if it's JSON
                    const parsed = JSON.parse(row.result);
                    // Common pattern: { value: "Positive" } or just "Positive"
                    resultStr = parsed.value || parsed.result || row.result;
                } catch (e) { }
            }

            return [
                row.patientId,
                row.gender,
                row.dob,
                `"${row.address || ''}"`, // Quote to handle commas
                row.testName,
                resultStr, // Result
                row.flags,
                row.date
            ].join(',');
        });

        const csvContent = csvHeader + csvRows.join('\n');

        return new NextResponse(csvContent, {
            status: 200,
            headers: {
                'Content-Type': 'text/csv',
                'Content-Disposition': `attachment; filename="epi-export-${new Date().toISOString().slice(0, 10)}.csv"`
            }
        });

    } catch (error) {
        console.error('Export error:', error);
        return NextResponse.json({ error: 'Export failed', details: String(error) }, { status: 500 });
    }
}
