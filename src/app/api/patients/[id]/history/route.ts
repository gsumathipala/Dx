import { NextResponse } from 'next/server';
import { readDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request, context: { params: Promise<{ id: string }> }) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const { id } = await context.params; // Next.js 15+ await params

    const db = await readDb();

    const patient = db.patients.find((p: any) => p.id === id);
    if (!patient) {
        return NextResponse.json({ error: 'Patient not found' }, { status: 404 });
    }

    // Find all orders for this patient
    const orders = db.orders.filter((o: any) => o.patientId === id);

    // Find all results linked to these orders
    const history = db.results.filter((r: any) =>
        orders.some((o: any) => o.id === r.orderId)
    ).sort((a: any, b: any) => new Date(a.performedAt).getTime() - new Date(b.performedAt).getTime());

    return NextResponse.json({
        patient,
        orders,
        history
    });
}
