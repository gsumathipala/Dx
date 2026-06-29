import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { v4 as uuidv4 } from 'uuid';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const type = searchParams.get('type');
    const db = await readDb();

    if (type === 'all') {
        return NextResponse.json(db.equipment || []);
    }
    else if (type === 'logs') {
        const equipmentId = searchParams.get('equipmentId');
        let logs = db.equipmentLogs || [];
        if (equipmentId) {
            logs = logs.filter((l: any) => l.equipmentId === equipmentId);
        }
        //Sort by timestamp desc
        logs.sort((a: any, b: any) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
        return NextResponse.json(logs.slice(0, 100)); // Limit 100
    }

    return NextResponse.json({ error: 'Invalid type' }, { status: 400 });
}

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const { type, data } = body;
        const db = await readDb();

        if (type === 'create_equipment') {
            if (!db.equipment) db.equipment = [];
            const newEq = { ...data, id: uuidv4() };
            db.equipment.push(newEq);
            await writeDb(db);
            return NextResponse.json(newEq);
        }
        else if (type === 'delete_equipment') {
            const { id } = data;
            if (db.equipment) {
                db.equipment = db.equipment.filter((e: any) => e.id !== id);
                if (db.equipmentLogs) {
                    db.equipmentLogs = db.equipmentLogs.filter((l: any) => l.equipmentId !== id);
                }
                await writeDb(db);
            }
            return NextResponse.json({ success: true });
        }
        else if (type === 'update_equipment') {
            const { id, ...updates } = data;
            const idx = db.equipment?.findIndex((e: any) => e.id === id);
            if (idx !== undefined && idx !== -1) {
                db.equipment[idx] = { ...db.equipment[idx], ...updates };
                await writeDb(db);
                return NextResponse.json(db.equipment[idx]);
            }
            return NextResponse.json({ error: 'Not found' }, { status: 404 });
        }
        else if (type === 'log_value') {
            if (!db.equipmentLogs) db.equipmentLogs = [];
            const newLog = {
                ...data,
                id: uuidv4(),
                timestamp: new Date().toISOString()
            };
            db.equipmentLogs.push(newLog);
            await writeDb(db);
            return NextResponse.json(newLog);
        }

        return NextResponse.json({ error: 'Invalid type' }, { status: 400 });
    } catch (error) {
        console.error(error);
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}
