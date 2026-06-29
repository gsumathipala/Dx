
import { readDb, writeDb } from '../lib/db';
import { db } from '../db';
import { users } from '../db/schema';
import { eq } from 'drizzle-orm';

async function testShim() {
    console.log('--- TESTING DB ADAPTER ---');

    // 1. Read
    console.log('Reading DB...');
    const data = await readDb();
    console.log(`Read ${data.users.length} users.`);

    // 2. Write (Upsert)
    console.log('Writing test user...');
    const testUser = {
        id: 'user-test-' + Date.now(),
        username: 'testuser',
        password: 'password',
        role: 'clerk',
        name: 'Test User',
        department: 'Reception'
    };

    data.users.push(testUser);

    await writeDb(data);
    console.log('Write complete.');

    // 3. Verify in SQL
    const result = await db.select().from(users).where(eq(users.id, testUser.id));
    if (result.length === 1 && result[0].username === 'testuser') {
        console.log('PASS: Test user persisted to SQLite.');
    } else {
        console.error('FAIL: User not found in SQLite.');
        process.exit(1);
    }
}

testShim().catch(e => {
    console.error(e);
    process.exit(1);
});
