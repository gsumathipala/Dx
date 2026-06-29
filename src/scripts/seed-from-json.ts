
import { db } from '../db';
import { users, patients, orders, results } from '../db/schema';
import fs from 'fs/promises';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';

async function main() {
    console.log('Starting migration...');

    const dataPath = path.join(process.cwd(), 'data', 'db.json');
    console.log('Reading data from:', dataPath);

    let jsonDb;
    try {
        const content = await fs.readFile(dataPath, 'utf-8');
        jsonDb = JSON.parse(content);
    } catch (e) {
        console.error('Could not read db.json:', e);
        return;
    }

    const toDate = (val: string | undefined) => val ? new Date(val) : new Date();

    console.log('Migrating users...');
    if (jsonDb.users?.length) {
        for (const u of jsonDb.users) {
            // Ensure all required fields exist
            if (!u.username || !u.password) {
                console.warn(`Skipping invalid user: ${u.id}`);
                continue;
            }
            await db.insert(users).values({
                id: u.id,
                username: u.username,
                password: u.password,
                role: u.role || 'user',
                name: u.name || u.username,
                department: u.department,
                createdAt: new Date()
            }).onConflictDoNothing();
        }
    }

    console.log('Migrating patients...');
    if (jsonDb.patients?.length) {
        for (const p of jsonDb.patients) {
            if (!p.name && !p.firstName) {
                console.warn(`Skipping invalid patient: ${p.id}`);
                continue;
            }
            const name = p.name || `${p.firstName} ${p.lastName}`;
            await db.insert(patients).values({
                id: p.id,
                name: name,
                dateOfBirth: p.dateOfBirth || '1900-01-01', // Validation required
                gender: p.gender || 'Unknown',
                contact: p.contact,
                address: p.address,
                insuranceProvider: p.insurance?.provider || null,
                insuranceId: p.insurance?.memberId || null,
                createdAt: new Date()
            }).onConflictDoNothing();
        }
    }

    console.log('Migrating orders...');
    if (jsonDb.orders?.length) {
        for (const o of jsonDb.orders) {
            // Handle array of tests -> string
            let testCode = o.testName;
            if (!testCode && o.tests && Array.isArray(o.tests)) testCode = o.tests.join(', ');
            if (!testCode && o.testIds && Array.isArray(o.testIds)) testCode = o.testIds.join(', ');
            if (!testCode) testCode = 'Unknown';

            let audit = [];
            if (Array.isArray(o.auditTrail)) audit = o.auditTrail;

            // Ensure patient exists? Drizzle might throw FK error if not.
            // We hope patient migration covered it.

            try {
                await db.insert(orders).values({
                    id: o.id,
                    patientId: o.patientId || 'UNKNOWN_PATIENT', // Risk here
                    testCode: testCode,
                    status: o.status || 'Pending',
                    collectionDate: toDate(o.timestamp),
                    createdAt: toDate(o.timestamp),
                    auditTrail: JSON.stringify(audit)
                }).onConflictDoNothing();
            } catch (err) {
                console.error(`Failed to migrate order ${o.id}:`, err);
            }
        }
    }

    console.log('Migrating results...');
    if (jsonDb.results?.length) {
        for (const r of jsonDb.results) {
            try {
                // Legacy 'results' entry seems to be a 'Report' container
                // It has 'values.notes' and 'values.results' map

                // 1. If it has values.results map, migrate those as individual results?
                // But we don't know the schema of the keys perfectly.

                // For now, migrate the legacy entry as a single row to preserve data
                // We'll use 'REPORT' as key if testId is missing

                let valueStr = r.value;
                if (!valueStr && r.values) valueStr = JSON.stringify(r.values);

                await db.insert(results).values({
                    id: r.id || uuidv4(),
                    orderId: r.orderId,
                    testId: r.testId || 'REPORT', // Fallback for constraint
                    value: valueStr,
                    unit: r.unit,
                    status: r.status || 'Verified',
                    flag: r.flag,
                    verifiedBy: r.verifiedBy || r.performedBy, // mapping aliases
                    releasedBy: r.releasedBy
                }).onConflictDoNothing();
            } catch (err) {
                console.error(`Failed to migrate result ${r.id}:`, err);
            }
        }
    }

    console.log('Migration complete!');
}

main().catch(console.error);
