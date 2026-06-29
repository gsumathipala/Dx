import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { db, client } from '@/db';
import { users } from '@/db/schema';
import { eq } from 'drizzle-orm';
import bcrypt from 'bcryptjs';
import { readDb, writeDb } from '@/lib/db';
import { v4 as uuidv4 } from 'uuid';

export async function POST(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const sessionUser = JSON.parse(session.value);

    if (sessionUser.role !== 'admin') {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { action, password, params } = body;

        // Verify admin password via Drizzle + bcrypt (replaces broken plaintext comparison)
        const [dbUser] = await db.select().from(users).where(eq(users.username, sessionUser.username)).limit(1);
        if (!dbUser || !(await bcrypt.compare(password, dbUser.password))) {
            return NextResponse.json({ error: 'Invalid password authorization.' }, { status: 401 });
        }

        switch (action) {
            case 'OPTIMIZE': {
                client.pragma('optimize');
                client.pragma('wal_checkpoint(PASSIVE)');
                return NextResponse.json({ success: true, message: 'Database optimized and WAL checkpoint completed.' });
            }

            case 'CHECK_INTEGRITY': {
                const rows = client.pragma('integrity_check') as Array<{ integrity_check: string }>;
                const ok = rows.length === 1 && rows[0].integrity_check === 'ok';
                return NextResponse.json({
                    success: ok,
                    message: ok ? 'Database integrity check passed.' : 'Integrity issues detected.',
                    details: rows
                });
            }

            case 'CLEAN_SESSIONS': {
                const result = client.prepare('DELETE FROM sessions WHERE expires_at < ?').run(Date.now());
                return NextResponse.json({
                    success: true,
                    message: `Expired sessions removed.`,
                    deleted: result.changes
                });
            }

            case 'ARCHIVE_LOGS': {
                const legacyDb = await readDb();
                const daysInfo = params?.retentionDays || 90;
                const cutoffDate = new Date();
                cutoffDate.setDate(cutoffDate.getDate() - daysInfo);

                const logsToArchive = legacyDb.auditLogs.filter((l: any) => new Date(l.timestamp) < cutoffDate);
                legacyDb.auditLogs = legacyDb.auditLogs.filter((l: any) => new Date(l.timestamp) >= cutoffDate);
                await writeDb(legacyDb);

                return NextResponse.json({
                    success: true,
                    message: `Archived ${logsToArchive.length} logs.`,
                    count: logsToArchive.length
                });
            }

            case 'SEED_DATA': {
                const legacyDb = await readDb();
                const newPatients = [
                    { id: uuidv4(), firstName: "Alice", lastName: "Johnson", dob: "1985-04-12", gender: "Female", email: "alice.j@example.com", mrn: `MRN-${Math.floor(Math.random() * 10000)}`, phone: null, address: null },
                    { id: uuidv4(), firstName: "Bob", lastName: "Smith", dob: "1990-08-23", gender: "Male", email: "bob.smith@example.com", mrn: `MRN-${Math.floor(Math.random() * 10000)}`, phone: null, address: null },
                    { id: uuidv4(), firstName: "Carol", lastName: "White", dob: "1978-11-05", gender: "Female", email: "carol.w@example.net", mrn: `MRN-${Math.floor(Math.random() * 10000)}`, phone: null, address: null },
                    { id: uuidv4(), firstName: "David", lastName: "Brown", dob: "2001-02-15", gender: "Male", email: "david.b@example.org", mrn: `MRN-${Math.floor(Math.random() * 10000)}`, phone: null, address: null },
                    { id: uuidv4(), firstName: "Eve", lastName: "Davis", dob: "1995-06-30", gender: "Female", email: "eve.d@example.com", mrn: `MRN-${Math.floor(Math.random() * 10000)}`, phone: null, address: null }
                ];

                legacyDb.patients.push(...newPatients);

                for (const p of newPatients) {
                    const orderId = `ORD-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
                    const testName = Math.random() > 0.5 ? 'Complete Blood Count' : 'Basic Metabolic Panel';
                    const testDef = legacyDb.testDefinitions.find((t: any) => t.name === testName);
                    const testId = testDef ? testDef.id : (testName === 'Complete Blood Count' ? 'cbc-code' : 'bmp-code');

                    legacyDb.orders.push({
                        id: orderId,
                        patientId: p.id,
                        accessionNumber: `ACC-${Date.now().toString().slice(-6)}-${Math.floor(Math.random() * 100)}`,
                        status: 'completed',
                        priority: 'Routine',
                        testIds: [testId],
                        timestamp: new Date().toISOString(),
                        orderBy: 'Dr. Seeder',
                        queueId: null,
                        completedAt: new Date().toISOString(),
                        updatedAt: new Date().toISOString()
                    });

                    const randomVal = (min: number, max: number) => (Math.random() * (max - min) + min).toFixed(1);
                    const resultValues = testName === 'Complete Blood Count'
                        ? { HGB: randomVal(11, 17), WBC: randomVal(3, 12), PLT: randomVal(140, 450) }
                        : { GLU: randomVal(65, 140), NA: randomVal(130, 150), K: randomVal(3.0, 5.5) };

                    legacyDb.results.push({
                        id: uuidv4(),
                        orderId,
                        testId,
                        values: { results: resultValues },
                        status: 'final',
                        resultFlags: {},
                        enteredBy: 'system',
                        timestamp: new Date().toISOString(),
                        technicalValidatedBy: 'system',
                        clinicalVerifiedBy: 'system',
                        comments: 'Auto-generated'
                    });
                }

                await writeDb(legacyDb);
                return NextResponse.json({ success: true, message: 'Demo data (5 patients, 5 orders) generated.' });
            }

            case 'FACTORY_RESET': {
                const legacyDb = await readDb();
                legacyDb.patients = [];
                legacyDb.orders = [];
                legacyDb.specimens = [];
                legacyDb.results = [];
                legacyDb.inventory = [];
                legacyDb.auditLogs = [];
                legacyDb.qcRuns = [];
                legacyDb.recordLocks = [];
                legacyDb.feedback = [];
                legacyDb.productionRuns = [];
                legacyDb.documents = [];
                legacyDb.histoBlocks = [];
                legacyDb.histoSlides = [];
                legacyDb.microCultures = [];
                legacyDb.emailQueue = [];
                legacyDb.users = legacyDb.users.filter((u: any) => u.username === sessionUser.username);
                await writeDb(legacyDb);
                return NextResponse.json({ success: true, message: 'System Factory Reset Complete.' });
            }

            default:
                return NextResponse.json({ error: 'Unknown action' }, { status: 400 });
        }

    } catch (error: any) {
        console.error('Maintenance error:', error);
        return NextResponse.json({ error: error.message || 'Maintenance failed' }, { status: 500 });
    }
}
