const Database = require('better-sqlite3');
const db = new Database('sqlite_v2.db');

try {
    // Check if column exists by querying table info
    const columns = db.pragma('table_info(authorization_queues)');
    const hasDeptColumn = columns.some(c => c.name === 'department');

    if (!hasDeptColumn) {
        db.exec("ALTER TABLE authorization_queues ADD COLUMN department TEXT DEFAULT 'General'");
        console.log('Added department column');
    } else {
        console.log('Department column already exists');
    }

    // Update any null values
    db.exec("UPDATE authorization_queues SET department = 'General' WHERE department IS NULL");
    console.log('Updated null departments to General');

} catch (e) {
    console.error('Error:', e.message);
}

db.close();
console.log('Done');
