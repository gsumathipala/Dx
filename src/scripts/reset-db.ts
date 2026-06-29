import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { migrate } from 'drizzle-orm/better-sqlite3/migrator';
import Database from 'better-sqlite3';
import { drizzle } from 'drizzle-orm/better-sqlite3';

const DB_FILE = 'sqlite_v2.db';
const MIGRATIONS_DIR = 'drizzle';

async function reset() {
    console.log('--- RESETTING DATABASE ---');

    // 1. Delete DB File
    if (fs.existsSync(DB_FILE)) {
        console.log('Deleting sqlite.db...');
        try {
            fs.unlinkSync(DB_FILE);
        } catch (e) {
            console.error('Failed to delete DB file (locked?):', e);
            process.exit(1);
        }
    }

    // 2. Delete Migrations
    if (fs.existsSync(MIGRATIONS_DIR)) {
        console.log('Deleting drizzle folder...');
        try {
            fs.rmSync(MIGRATIONS_DIR, { recursive: true, force: true });
        } catch (e) {
            console.error('Failed to delete migrations dir:', e);
        }
    }

    // 3. Generate Migrations
    console.log('Generating migrations...');
    try {
        execSync('npx drizzle-kit generate --config=drizzle.config.ts', { stdio: 'inherit' });
    } catch (e) {
        console.error('Failed to generate migrations:', e);
        process.exit(1);
    }

    // 4. Apply Migrations
    console.log('Applying migrations to new DB...');
    const sqlite = new Database(DB_FILE);
    const db = drizzle(sqlite);
    try {
        await migrate(db, { migrationsFolder: MIGRATIONS_DIR });
        console.log('Migrations applied!');
    } catch (e) {
        console.error('Failed to apply migrations:', e);
        process.exit(1);
    }

    console.log('--- DB SETUP COMPLETE ---');
}

reset();
