import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { cookies } from 'next/headers';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const { searchParams } = new URL(request.url);
    const query = searchParams.get('q');

    if (!query) return NextResponse.json([]);

    const db = await readDb();
    const queryLower = query.toLowerCase();

    // Search Specimens
    const specimens = (db.specimens || []).map((spec: any) => {
        const order = (db.orders || []).find((o: any) => o.id === spec.orderId);
        const patient = order ? (db.patients || []).find((p: any) => p.id === order.patientId) : null;
        return { ...spec, patientName: patient ? `${patient.firstName} ${patient.lastName}` : 'Unknown', patientMrn: patient?.mrn };
    });

    const matches = specimens.filter((s: any) =>
        s.id.toLowerCase().includes(queryLower) ||
        s.patientName.toLowerCase().includes(queryLower) ||
        (s.patientMrn && s.patientMrn.toLowerCase().includes(queryLower))
    );

    const enriched = matches.map((s: any) => {
        const history = (db.auditLogs || [])
            .filter((log: any) => log.recordId === s.id)
            .sort((a: any, b: any) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

        return { ...s, history };
    });

    return NextResponse.json(enriched);
}

export async function POST(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const user = JSON.parse(session.value);

    // Only authorized staff can update custody
    if (!['admin', 'manager', 'scientist', 'clerk', 'medic'].includes(user.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const { specimenId, action, location, condition, temperature, notes } = await request.json();
        const db = await readDb();
        const specimen = db.specimens.find((s: any) => s.id === specimenId);

        if (!specimen) return NextResponse.json({ error: 'Specimen not found' }, { status: 404 });

        const previousData = { ...specimen };

        // Update Fields
        if (location) specimen.location = location;

        // Status updates based on action
        if (action === 'CHECK_IN') specimen.status = 'stored';
        if (action === 'DISPOSE') specimen.status = 'disposed';
        if (action === 'REJECT') specimen.status = 'rejected';
        if (action === 'CHECK_OUT') specimen.status = 'in-transit';

        // Audit Log (The Core of Chain of Custody)
        // We merged details into the audit action or similar, or just relying on diff.
        // But for tracking, we might want to capture temp/notes.
        // My logAudit in db.ts only takes (previous, new).
        // I'll attach notes to the specimen object temporarily? No that's bad.
        // I'll accept that temperature/notes are lost in structured audit unless I change logAudit.
        // OR I can put them in `details` property of log if I manually push to `auditLogs`?
        // But I should use `logAudit` helper.
        // The helper writes `details: JSON.stringify({ previous, new })`.
        // If I modify `specimen` to include `_meta: { notes, temp }`?
        // It won't be saved to DB if schema doesn't have it, but it WILL be JSON-stringified in audit log.
        // Hacky but works.
        const metaSpecimen = { ...specimen, _meta: { temperature, notes, condition } };

        await logAudit(db, 'Specimen', specimenId, action, previousData, metaSpecimen, user.username);
        await writeDb(db);

        return NextResponse.json({ success: true });
    } catch (e: any) {
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
