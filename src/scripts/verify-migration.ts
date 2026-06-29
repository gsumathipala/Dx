import { db } from '../db';
import { users, patients, orders, results } from '../db/schema';
import { count } from 'drizzle-orm';

async function verify() {
    const userCount = await db.select({ value: count() }).from(users);
    const patientCount = await db.select({ value: count() }).from(patients);
    const orderCount = await db.select({ value: count() }).from(orders);
    const resultCount = await db.select({ value: count() }).from(results);

    console.log('--- MIGRATION VERIFICATION ---');
    console.log(`Users: ${userCount[0].value}`);
    console.log(`Patients: ${patientCount[0].value}`);
    console.log(`Orders: ${orderCount[0].value}`);
    console.log(`Results: ${resultCount[0].value}`);

    if (userCount[0].value === 0 && patientCount[0].value === 0) {
        console.error('FAIL: Database is empty.');
        process.exit(1);
    } else {
        console.log('PASS: Data present.');
    }
}

verify().catch(console.error);
