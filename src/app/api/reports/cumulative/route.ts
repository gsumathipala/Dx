import { NextResponse } from 'next/server';
import { db } from '@/db';
import { orders, results, patients, testDefinitions } from '@/db/schema';
import { eq, and, inArray } from 'drizzle-orm';
import { cookies } from 'next/headers';

export async function GET(request: Request) {
    try {
        const cookieStore = await cookies();
        const session = cookieStore.get('auth_session');
        if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

        const { searchParams } = new URL(request.url);
        const patientId = searchParams.get('patientId');
        const testCodesParam = searchParams.get('testCodes');

        if (!patientId) {
            return NextResponse.json({ error: 'patientId is required' }, { status: 400 });
        }

        // Fetch patient
        const [patient] = await db
            .select()
            .from(patients)
            .where(eq(patients.id, patientId))
            .limit(1);

        if (!patient) {
            return NextResponse.json({ error: 'Patient not found' }, { status: 404 });
        }

        // Fetch all completed orders for this patient, sorted by date
        const patientOrders = await db
            .select()
            .from(orders)
            .where(and(eq(orders.patientId, patientId), eq(orders.status, 'Completed')))
            .orderBy(orders.timestamp);

        if (patientOrders.length === 0) {
            return NextResponse.json({
                patient: {
                    name: `${patient.firstName} ${patient.lastName}`,
                    mrn: patient.mrn,
                    dob: patient.dob,
                    gender: patient.gender,
                },
                tests: [],
                visits: [],
            });
        }

        const orderIds = patientOrders.map((o) => o.id);

        // Fetch all results for these orders
        const allResults = await db
            .select()
            .from(results)
            .where(inArray(results.orderId, orderIds));

        // Collect all unique testIds
        const testIdSet = new Set<string>(allResults.map((r) => r.testId));
        const testIdArr = Array.from(testIdSet);

        // Fetch test definitions
        let testDefs: typeof testDefinitions.$inferSelect[] = [];
        if (testIdArr.length > 0) {
            testDefs = await db
                .select()
                .from(testDefinitions)
                .where(inArray(testDefinitions.id, testIdArr));
        }

        // Filter by testCodes if provided
        let filteredTestDefs = testDefs;
        if (testCodesParam) {
            const codes = testCodesParam.split(',').map((c) => c.trim().toUpperCase());
            filteredTestDefs = testDefs.filter((td) => codes.includes(td.code.toUpperCase()));
        }

        const testDefMap = new Map(testDefs.map((td) => [td.id, td]));

        // Build tests array
        const testsArr = filteredTestDefs.map((td) => ({
            testId: td.id,
            testCode: td.code,
            testName: td.name,
            units: td.units ?? '',
            referenceRange: td.referenceRange ? (() => { try { return JSON.parse(td.referenceRange!); } catch { return td.referenceRange; } })() : null,
        }));

        const allowedTestIds = new Set(filteredTestDefs.map((td) => td.id));

        // Build visits array
        const visits = patientOrders.map((order) => {
            const orderResults = allResults.filter(
                (r) => r.orderId === order.id && allowedTestIds.has(r.testId)
            );

            const resultsByCode: Record<string, { value: string; status: string; flags: string[] }> = {};
            for (const r of orderResults) {
                const td = testDefMap.get(r.testId);
                if (!td) continue;
                let value = '';
                if (r.values) {
                    try {
                        const parsed = JSON.parse(r.values);
                        value = parsed.value ?? String(parsed);
                    } catch {
                        value = r.values;
                    }
                }
                let flags: string[] = [];
                if (r.resultFlags) {
                    try {
                        flags = JSON.parse(r.resultFlags);
                    } catch {
                        flags = [r.resultFlags];
                    }
                }
                resultsByCode[td.code] = {
                    value,
                    status: r.status ?? '',
                    flags,
                };
            }

            return {
                orderId: order.id,
                accessionNumber: order.accessionNumber,
                date: order.completedAt ?? order.timestamp,
                results: resultsByCode,
            };
        });

        // Sort visits newest first for display
        visits.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

        return NextResponse.json({
            patient: {
                name: `${patient.firstName} ${patient.lastName}`,
                mrn: patient.mrn,
                dob: patient.dob,
                gender: patient.gender,
            },
            tests: testsArr,
            visits,
        });
    } catch (error) {
        console.error('Cumulative report error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
