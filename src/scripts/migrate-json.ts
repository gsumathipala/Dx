
import fs from 'fs';
import path from 'path';
import { db } from '../db';
import { users, patients, orders, results, testDefinitions, systemAlerts, auditLogs, specimens } from '../db/schema';
import { v4 as uuidv4 } from 'uuid';

async function migrate() {
    console.log('Starting migration...');

    // Read JSON DB
    const jsonPath = path.join(process.cwd(), 'data', 'db.json');
    if (!fs.existsSync(jsonPath)) {
        console.error('db.json not found!');
        return;
    }
    const rawData = fs.readFileSync(jsonPath, 'utf8');
    const jsonData = JSON.parse(rawData);

    // 1. Users
    if (jsonData.users?.length) {
        console.log(`Migrating ${jsonData.users.length} users...`);
        for (const u of jsonData.users) {
            await db.insert(users).values({
                id: u.id,
                username: u.username,
                password: u.password,
                role: u.role,
                name: u.name,
                department: u.department,
                email: u.email
            }).onConflictDoNothing();
        }
    }

    // 2. Patients
    if (jsonData.patients?.length) {
        console.log(`Migrating ${jsonData.patients.length} patients...`);
        for (const p of jsonData.patients) {
            await db.insert(patients).values({
                id: p.id,
                firstName: p.firstName,
                lastName: p.lastName,
                dob: p.dob,
                gender: p.gender,
                mrn: p.mrn,
                email: p.email,
                phone: p.phone,
                address: p.address
            }).onConflictDoNothing();
        }
    }

    // 3. Orders
    if (jsonData.orders?.length) {
        console.log(`Migrating ${jsonData.orders.length} orders...`);
        for (const o of jsonData.orders) {
            try {
                await db.insert(orders).values({
                    id: o.id,
                    patientId: o.patientId,
                    accessionNumber: o.accessionNumber,
                    status: o.status,
                    orderBy: o.orderBy,
                    timestamp: o.timestamp,
                    queueId: o.queueId,
                    priority: o.priority || 'Routine',
                    completedAt: o.completedAt,
                    testIds: JSON.stringify(o.testIds)
                }).onConflictDoNothing();
            } catch (e: any) {
                console.error(`Skipping order ${o.id}: ${e.message}`);
            }
        }
    }

    // 4. Test Definitions
    if (jsonData.testDefinitions?.length) {
        console.log(`Migrating ${jsonData.testDefinitions.length} test definitions...`);
        for (const t of jsonData.testDefinitions) {
            await db.insert(testDefinitions).values({
                id: t.id,
                code: t.code,
                name: t.name,
                department: t.department,
                units: t.units,
                tatHours: t.tatHours,
                active: t.active,
                referenceRange: JSON.stringify(t.referenceRange),
                specimenTypes: JSON.stringify(t.specimenTypes),
                methodology: t.methodology
            }).onConflictDoNothing();
        }
    }

    // 5. Results
    if (jsonData.results?.length) {
        console.log(`Migrating ${jsonData.results.length} results...`);
        for (const r of jsonData.results) {
            try {
                await db.insert(results).values({
                    id: r.id,
                    orderId: r.orderId,
                    testId: r.testId || 'unknown',
                    values: JSON.stringify(r.values),
                    resultFlags: JSON.stringify(r.resultFlags),
                    status: r.status,
                    enteredBy: r.enteredBy,
                    technicalValidatedBy: r.technicalValidatedBy,
                    clinicalVerifiedBy: r.clinicalVerifiedBy,
                    timestamp: r.timestamp
                }).onConflictDoNothing();
            } catch (e: any) {
                console.error(`Failed result ${r.id}: ${e.message}`);
                throw e; // Fail fast for now to see first error
            }
        }
    }

    // 6. Specimens (New Table)
    if (jsonData.specimens?.length) {
        console.log(`Migrating ${jsonData.specimens.length} specimens...`);
        for (const s of jsonData.specimens) {
            await db.insert(specimens).values({
                id: s.id,
                orderId: s.orderId,
                type: s.type,
                containerId: s.containerId,
                location: s.location,
                collectionDate: s.collectionDate,
                status: s.status
            }).onConflictDoNothing();
        }
    }

    // 7. Alerts
    if (jsonData.systemAlerts?.length) {
        console.log(`Migrating ${jsonData.systemAlerts.length} alerts...`);
        for (const a of jsonData.systemAlerts) {
            try {
                await db.insert(systemAlerts).values({
                    id: a.id,
                    message: a.message,
                    type: a.type,
                    active: a.active,
                    createdAt: a.createdAt,
                    readBy: JSON.stringify(a.readBy),
                    timeout: a.timeout
                }).onConflictDoNothing();
            } catch (e: any) {
                console.error(`Error processing alert ${a.id}: ${e.message}`);
            }
        }
    }

    console.log('Migration complete!');
}

migrate().catch(e => console.error("Fatal migration error:", e.message));
