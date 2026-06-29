import Database from 'better-sqlite3';
import { drizzle } from 'drizzle-orm/better-sqlite3';
import * as schema from './schema';

const sqlite = new Database('sqlite_v2.db');
export const db = drizzle(sqlite, { schema });

// Export the raw client for raw queries if needed
export const client = sqlite;
