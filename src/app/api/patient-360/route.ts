import { NextResponse } from 'next/server';
import { readDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const query = searchParams.get('q'); // Name or MRN
    const patientId = searchParams.get('id');

    const db = await readDb();

    if (patientId) {
        // Fetch Single Patient Full History
        const patient = db.patients.find((p: any) => p.id === patientId);
        if (!patient) return NextResponse.json({ error: 'Patient not found' }, { status: 404 });

        // Find all orders for this patient
        const orders = db.orders.filter((o: any) => o.patientId === patientId).sort((a: any, b: any) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

        // Find all results linked to these orders
        const orderIds = orders.map((o: any) => o.id);
        const results = db.results.filter((r: any) => orderIds.includes(r.orderId));

        // Aggregate Micro & Histo if present
        const micro = db.microCultures ? db.microCultures.filter((m: any) => orderIds.includes(m.orderId)) : [];
        const histo = db.histoBlocks ? db.histoBlocks.filter((h: any) => h.accessionNumber.startsWith(orders.find((o: any) => o.id === h.orderId || true)?.accessionNumber?.split('-')[0] || 'INVALID')) : [];
        // Note: Histo linking is weak in this prototype (via accession number matching), simplifying for now by just returning empty or attempting match if possible.
        // Better: Find orders with accession numbers matching histo blocks.

        return NextResponse.json({ patient, orders, results, micro });
    }

    if (query) {
        // Search Mode
        const q = query.toLowerCase();
        const matches = db.patients.filter((p: any) => {
            const fullName = `${p.firstName || ''} ${p.lastName || ''}`.toLowerCase();
            return fullName.includes(q) || (p.mrn && p.mrn.toLowerCase().includes(q));
        }).slice(0, 10);
        return NextResponse.json(matches);
    }

    return NextResponse.json([]);
}
