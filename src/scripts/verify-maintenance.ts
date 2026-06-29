
import { db } from '../db';
import { sql } from 'drizzle-orm';

async function verifyMaintenance() {
    console.log('--- Verifying Maintenance Commands ---');

    // 1. Check Integrity
    console.log('1. Running Integrity Check...');
    try {
        const checkResult = await db.get(sql`PRAGMA integrity_check`);
        console.log('   Result:', checkResult);
    } catch (e: any) {
        console.error('   ❌ Failed:', e.message);
    }

    // 2. Vacuum
    console.log('2. Running VACUUM (Optimization)...');
    try {
        await db.run(sql`VACUUM`);
        console.log('   ✅ Success: VACUUM completed.');
    } catch (e: any) {
        console.error('   ❌ Failed:', e.message);
    }
}

verifyMaintenance().catch(console.error);
