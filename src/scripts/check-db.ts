
import { db } from '../db';
import { users } from '../db/schema';

async function main() {
    console.log('Checking database connection...');
    try {
        const result = await db.select().from(users).limit(1);
        console.log('Connection successful. Users found:', result.length);
    } catch (error) {
        console.error('Database check failed:', error);
    }
}

main();
