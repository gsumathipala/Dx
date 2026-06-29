const Database = require('better-sqlite3');
const path = require('path');

const db = new Database(path.join(__dirname, '..', '..', 'sqlite_v2.db'));

const statements = [
  `CREATE TABLE IF NOT EXISTS calculated_tests (
    id TEXT PRIMARY KEY NOT NULL,
    test_code TEXT NOT NULL,
    name TEXT NOT NULL,
    formula TEXT NOT NULL,
    unit TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
  )`,
  `CREATE UNIQUE INDEX IF NOT EXISTS calculated_tests_test_code_unique ON calculated_tests (test_code)`,
  `CREATE TABLE IF NOT EXISTS critical_value_notifications (
    id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    test_id TEXT NOT NULL,
    test_code TEXT NOT NULL,
    value TEXT NOT NULL,
    threshold TEXT NOT NULL,
    critical_type TEXT NOT NULL,
    status TEXT DEFAULT 'Pending' NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS critical_value_acknowledgments (
    id TEXT PRIMARY KEY NOT NULL,
    notification_id TEXT NOT NULL,
    acknowledged_by TEXT NOT NULL,
    acknowledged_at TEXT NOT NULL,
    notified_clinician TEXT,
    notification_method TEXT,
    notes TEXT,
    escalated_to TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS delta_check_rules (
    id TEXT PRIMARY KEY NOT NULL,
    test_id TEXT NOT NULL,
    test_code TEXT NOT NULL,
    delta_type TEXT NOT NULL,
    threshold REAL NOT NULL,
    direction TEXT DEFAULT 'any' NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    created_by TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS delta_check_flags (
    id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL,
    test_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    previous_order_id TEXT,
    previous_value REAL,
    current_value REAL NOT NULL,
    delta_percent REAL,
    delta_absolute REAL,
    flagged_at TEXT NOT NULL,
    acknowledged_by TEXT,
    acknowledged_at TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS demographic_reference_ranges (
    id TEXT PRIMARY KEY NOT NULL,
    test_id TEXT NOT NULL,
    test_code TEXT NOT NULL,
    age_min INTEGER,
    age_max INTEGER,
    gender TEXT DEFAULT 'All',
    pregnancy INTEGER DEFAULT 0,
    trimester INTEGER,
    low_normal REAL,
    high_normal REAL,
    low_critical REAL,
    high_critical REAL,
    unit TEXT,
    notes TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS reflex_rules (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    trigger_test_id TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    add_test_id TEXT NOT NULL,
    add_test_code TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    created_by TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS reflex_activations (
    id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    trigger_value TEXT NOT NULL,
    new_test_id TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    status TEXT DEFAULT 'Pending' NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS result_signatures (
    id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL,
    signed_by TEXT NOT NULL,
    signed_at TEXT NOT NULL,
    signature_type TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS tat_thresholds (
    id TEXT PRIMARY KEY NOT NULL,
    scope TEXT NOT NULL,
    scope_id TEXT,
    target_hours REAL NOT NULL,
    warning_hours REAL NOT NULL,
    breach_hours REAL NOT NULL,
    priority TEXT DEFAULT 'Routine',
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS tat_breaches (
    id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL,
    actual_hours REAL NOT NULL,
    target_hours REAL NOT NULL,
    breach_type TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    resolved_at TEXT,
    notified_at TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS user_competencies (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL,
    test_id TEXT,
    category TEXT,
    competency_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    assessed_by TEXT NOT NULL,
    status TEXT DEFAULT 'Active' NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS retention_policies (
    id TEXT PRIMARY KEY NOT NULL,
    specimen_type TEXT NOT NULL,
    retention_days INTEGER NOT NULL,
    temperature TEXT,
    disposal_method TEXT DEFAULT 'Biohazard Disposal' NOT NULL,
    active INTEGER DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS specimen_disposals (
    id TEXT PRIMARY KEY NOT NULL,
    specimen_id TEXT NOT NULL,
    policy_id TEXT,
    disposed_at TEXT NOT NULL,
    disposed_by TEXT NOT NULL,
    batch_number TEXT,
    notes TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS requesters (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    fax TEXT,
    address TEXT,
    delivery_preference TEXT DEFAULT 'portal',
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    notes TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS distribution_rules (
    id TEXT PRIMARY KEY NOT NULL,
    requester_id TEXT,
    test_id TEXT,
    method TEXT NOT NULL,
    destination TEXT,
    auto_release INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS distribution_logs (
    id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL,
    rule_id TEXT,
    method TEXT NOT NULL,
    destination TEXT,
    sent_at TEXT,
    status TEXT DEFAULT 'Pending' NOT NULL,
    error TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS notifiable_conditions (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    organism TEXT,
    test_ids TEXT,
    reporting_body TEXT NOT NULL,
    timeframe TEXT DEFAULT '24h' NOT NULL,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS epidemiology_notifications (
    id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    status TEXT DEFAULT 'Pending' NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    submitted_by TEXT,
    submitted_at TEXT,
    notes TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS phlebotomy_schedules (
    id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    order_id TEXT,
    ward_location TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    collection_type TEXT DEFAULT 'Routine' NOT NULL,
    test_ids TEXT,
    assigned_to TEXT,
    status TEXT DEFAULT 'Scheduled' NOT NULL,
    notes TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS loinc_codes (
    id TEXT PRIMARY KEY NOT NULL,
    loinc_code TEXT NOT NULL,
    long_name TEXT NOT NULL,
    short_name TEXT,
    component TEXT,
    property TEXT,
    time_aspect TEXT,
    system TEXT,
    scale TEXT,
    method TEXT,
    status TEXT DEFAULT 'Active'
  )`,
  `CREATE UNIQUE INDEX IF NOT EXISTS loinc_codes_loinc_code_unique ON loinc_codes (loinc_code)`,
  `CREATE TABLE IF NOT EXISTS specimen_receiving (
    id TEXT PRIMARY KEY NOT NULL,
    specimen_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    received_by TEXT NOT NULL,
    condition TEXT DEFAULT 'Acceptable' NOT NULL,
    condition_notes TEXT,
    rejection_reason TEXT,
    temperature TEXT,
    volume REAL,
    status TEXT DEFAULT 'Accepted' NOT NULL
  )`
];

let ok = 0;
let skip = 0;
for (const sql of statements) {
  try {
    db.exec(sql);
    ok++;
  } catch (e) {
    if (e.message && e.message.includes('already exists')) {
      skip++;
    } else {
      console.error('ERROR:', e.message, '\nSQL:', sql.substring(0, 80));
      process.exit(1);
    }
  }
}

console.log(`Done. Created: ${ok}, Skipped (already exists): ${skip}`);
db.close();
