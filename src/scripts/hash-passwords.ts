
import { db } from '../db';
import { users } from '../db/schema';
import { eq } from 'drizzle-orm';
import bcrypt from 'bcryptjs';

async function hashPasswords() {
    console.log('--- MIGRATING PASSWORDS TO BCRYPT ---');

    // 1. Fetch all users
    const allUsers = await db.select().from(users);
    console.log(`Found ${allUsers.length} users.`);

    let updatedCount = 0;

    for (const user of allUsers) {
        // Check if already hashed (bcrypt hashes start with $2a$, $2b$, or $2y$)
        if (user.password.startsWith('$2a$') || user.password.startsWith('$2b$') || user.password.startsWith('$2y$')) {
            console.log(`Skipping ${user.username} (already hashed)`);
            continue;
        }

        console.log(`Hashing password for ${user.username}...`);
        const salt = await bcrypt.genSalt(10);
        const hashedPassword = await bcrypt.hash(user.password, salt);

        await db.update(users)
            .set({ password: hashedPassword })
            .where(eq(users.id, user.id));

        updatedCount++;
    }

    console.log(`--- COMPLETE: Updated ${updatedCount} users ---`);
}

hashPasswords().catch(e => {
    console.error("Fatal error:", e);
    process.exit(1);
});
