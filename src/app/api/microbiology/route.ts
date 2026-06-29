import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const orderId = searchParams.get('orderId');
    const type = searchParams.get('type');
    const db = await readDb();

    if (type === 'config') {
        return NextResponse.json({ antibiotics: db.antibiotics || [] });
    }

    let cultures = db.microCultures || [];
    if (orderId) {
        cultures = cultures.filter((c: any) => c.orderId === orderId);
    }
    return NextResponse.json(cultures);
}

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();

        if (body.type === 'update_config') {
            const db = await readDb();
            if (body.antibiotics && Array.isArray(body.antibiotics)) {
                db.antibiotics = body.antibiotics;
                await writeDb(db);
                return NextResponse.json({ success: true });
            }
            return NextResponse.json({ error: 'Invalid config' }, { status: 400 });
        }

        const { orderId, organism, growth, sensitivity, dayReadings, finalReport } = body;
        // sensitivity: { "Amoxicillin": "S", "Gentamicin": "R" }
        // dayReadings: { "Day 1": "No Growth", "Day 2": "Scanty Growth" }

        const db = await readDb();
        if (!db.microCultures) db.microCultures = [];

        const cultureIdx = db.microCultures.findIndex((c: any) => c.orderId === orderId);

        // Infection Control Logic (LabCentre Feature)
        const epiAlerts = [];
        if (organism?.includes('MRSA') || organism?.includes('VRE') || organism?.includes('C. diff')) {
            epiAlerts.push('MDRO DETECTED - CONTACT ISOLATION ADVISED');
        }

        const cultureRecord = {
            id: cultureIdx >= 0 ? db.microCultures[cultureIdx].id : Date.now().toString(),
            orderId,
            organism,
            growth,
            sensitivity,
            dayReadings,
            epiAlerts,
            updatedAt: new Date().toISOString()
        };

        if (cultureIdx >= 0) db.microCultures[cultureIdx] = cultureRecord;
        else db.microCultures.push(cultureRecord);

        // Sync to Main Result Text (so it appears on standard reports)
        if (finalReport) {
            const order = db.orders.find((o: any) => o.id === orderId);
            if (order) {
                // Update Order Status to partially reflect progress? 
                // Maybe not, usually Micro is one test in an order. 
                // We'll update the RESULT entry for the "Culture" test.
                // Finding the 'Culture' test ID is tricky without knowing it, 
                // so we'll append to the General Report Notes for now.

                const resultIdx = db.results.findIndex((r: any) => r.orderId === orderId);
                let reportText = `\n--- MICROBIOLOGY REPORT ---\nOrganism: ${organism || 'None'}\nGrowth: ${growth || 'N/A'}\n`;

                if (Object.keys(sensitivity || {}).length > 0) {
                    reportText += `\nANTIBIOGRAM:\n`;
                    for (const [abx, res] of Object.entries(sensitivity)) {
                        reportText += `${abx}: ${res}\n`;
                    }
                }

                if (epiAlerts.length > 0) {
                    reportText += `\n*** ${epiAlerts.join(' ')} ***\n`;
                }

                if (resultIdx >= 0) {
                    // Append/Replace notes
                    if (!db.results[resultIdx].values.notes) db.results[resultIdx].values.notes = '';
                    // Simple replace strategy for demo to avoid duplicates
                    const existingNotes = db.results[resultIdx].values.notes;
                    if (!existingNotes.includes('--- MICROBIOLOGY REPORT ---')) {
                        db.results[resultIdx].values.notes += reportText;
                    } else {
                        // Very basic update: just append nicely if not too cluttered
                        // Ideally we'd replace the block, but append is safer for data loss
                        db.results[resultIdx].values.notes += `\n(Updated Micro): ${organism}`;
                    }
                } else {
                    // Create result if empty
                    db.results.push({
                        id: Date.now().toString() + "_micro",
                        orderId,
                        values: { results: {}, notes: reportText },
                        timestamp: new Date().toISOString(),
                        performedBy: 'Microbiology Dept',
                        status: 'Preliminary'
                    });
                }
            }
        }

        await writeDb(db);
        return NextResponse.json(cultureRecord);

    } catch (error) {
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}
