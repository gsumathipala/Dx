import { migrate } from 'drizzle-orm/better-sqlite3/migrator';
import { db } from '../db';

// This will run migrations on the database, skipping the ones already applied
async function runMigrations() {
    console.log('Applying migrations...');
    try {
        await migrate(db, { migrationsFolder: 'drizzle' });
        console.log('Migrations applied successfully!');
    } catch (error) {
        console.error('Migration failed:', error);
        process.exit(1);
    }
}

runMigrations();
