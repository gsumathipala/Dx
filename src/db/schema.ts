import { sqliteTable, text, integer, real, uniqueIndex } from 'drizzle-orm/sqlite-core';

// === USERS & AUTH ===
export const users = sqliteTable('users', {
    id: text('id').primaryKey(),
    username: text('username').notNull().unique(),
    password: text('password').notNull(),
    role: text('role').notNull(),
    name: text('name').notNull(),
    department: text('department'),
    email: text('email')
});

// === DEPARTMENTS ===
export const departments = sqliteTable('departments', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    code: text('code').notNull().unique(),
    type: text('type').notNull().default('clinical'),
    description: text('description'),
    enabled: integer('enabled', { mode: 'boolean' }).default(true),
    createdAt: text('created_at'),
    lastModifiedAt: text('last_modified_at'),
    lastModifiedBy: text('last_modified_by')
});

export const sessions = sqliteTable('sessions', {
    id: text('id').primaryKey(),
    userId: text('user_id').notNull().references(() => users.id),
    token: text('token').notNull().unique(),
    expiresAt: integer('expires_at').notNull()
});

// === PATIENTS ===
export const patients = sqliteTable('patients', {
    id: text('id').primaryKey(),
    firstName: text('first_name').notNull(),
    lastName: text('last_name').notNull(),
    dob: text('dob').notNull(),
    gender: text('gender').notNull(),
    mrn: text('mrn').notNull().unique(),
    email: text('email'),
    phone: text('phone'),
    address: text('address')
});

// === ORDERS ===
export const orders = sqliteTable('orders', {
    id: text('id').primaryKey(),
    patientId: text('patient_id').notNull().references(() => patients.id),
    accessionNumber: text('accession_number').notNull().unique(),
    status: text('status').notNull(), // Pending, In Progress, Completed
    orderBy: text('order_by'),
    timestamp: text('timestamp').notNull(),
    queueId: text('queue_id'),
    priority: text('priority').default('Routine'),
    completedAt: text('completed_at'),
    updatedAt: text('updated_at'),
    testIds: text('test_ids') // JSON stringified array for now to match legacy
});

// === SPECIMENS ===
export const specimens = sqliteTable('specimens', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull().references(() => orders.id),
    type: text('type').notNull(),
    containerId: text('container_id'),
    location: text('location'),
    collectionDate: text('collection_date'),
    status: text('status')
});

// === RESULTS ===
export const results = sqliteTable('results', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull().references(() => orders.id),
    testId: text('test_id').notNull(),
    // Storing complex value objects as JSON strings for the initial migration
    // to avoid over-engineering the relational model immediately
    values: text('values'), // Can be null in legacy data apparently
    resultFlags: text('result_flags'), // JSON
    status: text('status'),
    enteredBy: text('entered_by'),
    technicalValidatedBy: text('technical_validated_by'),
    clinicalVerifiedBy: text('clinical_verified_by'),
    comments: text('comments'),
    timestamp: text('timestamp').notNull()
}, (table) => ({
    orderTestUnique: uniqueIndex('results_order_test_unique').on(table.orderId, table.testId)
}));

// === CONFIG: TEST DEFINITIONS ===
export const testDefinitions = sqliteTable('test_definitions', {
    id: text('id').primaryKey(),
    code: text('code').notNull().unique(),
    name: text('name').notNull(),
    department: text('department').notNull(),
    units: text('units'),
    tatHours: real('tat_hours'),
    active: integer('active', { mode: 'boolean' }).default(true),
    // JSON fields for complex structures
    referenceRange: text('reference_range'),
    specimenTypes: text('specimen_types'),
    methodology: text('methodology'),
    loincCode: text('loinc_code')
});

// === SYSTEM: QUEUES ===
export const authorizationQueues = sqliteTable('authorization_queues', {
    id: text('id').primaryKey(),
    name: text('name').notNull().unique(),
    description: text('description'),
    department: text('department').default('General'), // Department this queue belongs to
    allowedRoles: text('allowed_roles'), // JSON array
    createdBy: text('created_by'),
    createdAt: text('created_at')
});

// === SYSTEM: AUDIT LOGS ===
export const auditLogs = sqliteTable('audit_logs', {
    id: text('id').primaryKey(),
    entityType: text('entity_type').notNull(),
    entityId: text('entity_id').notNull(),
    action: text('action').notNull(),
    userId: text('user_id').notNull(),
    timestamp: text('timestamp').notNull(),
    details: text('details') // JSON of diff/changes
});

// === SYSTEM: ALERTS ===
export const systemAlerts = sqliteTable('system_alerts', {
    id: text('id').primaryKey(),
    message: text('message').notNull(),
    type: text('type').notNull(), // info, warning, error
    active: integer('active', { mode: 'boolean' }).default(true),
    createdAt: text('created_at').notNull(),
    readBy: text('read_by'), // JSON array of usernames
    timeout: integer('timeout')
});

// === BILLING ===
export const billingItems = sqliteTable('billing_items', {
    id: text('id').primaryKey(),
    code: text('code').notNull().unique(), // CPT-4 or internal code
    name: text('name').notNull(),
    price: real('price').notNull(),
    active: integer('active', { mode: 'boolean' }).default(true)
});

export const invoices = sqliteTable('invoices', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull().references(() => orders.id),
    totalAmount: real('total_amount').notNull(),
    status: text('status').notNull(), // Pending, Paid, Canceled
    createdAt: text('created_at').notNull(),
    items: text('items') // JSON: [{ code, price, description }]
});

// === INVENTORY ===
export const inventoryItems = sqliteTable('inventory_items', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    lotNumber: text('lot_number'),
    expirationDate: text('expiration_date'),
    quantity: integer('quantity').notNull().default(0),
    unit: text('unit').notNull(),
    minThreshold: integer('min_threshold').default(10),
    location: text('location')
});

export const inventoryTransactions = sqliteTable('inventory_transactions', {
    id: text('id').primaryKey(),
    itemId: text('item_id').notNull().references(() => inventoryItems.id),
    change: integer('change').notNull(), // + for restock, - for usage
    reason: text('reason').notNull(),
    userId: text('user_id').notNull(),
    timestamp: text('timestamp').notNull()
});

// === CONFIG: REJECTION CRITERIA ===
export const rejectionCriteria = sqliteTable('rejection_criteria', {
    id: text('id').primaryKey(),
    reason: text('reason').notNull(),
    description: text('description'),
    category: text('category').default('General'), // Quantity, Quality, Labeling
    active: integer('active', { mode: 'boolean' }).default(true)
});

// === QC ===
export const qcMaterials = sqliteTable('qc_materials', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    lotNumber: text('lot_number').notNull(),
    expirationDate: text('expiration_date').notNull(),
    manufacturer: text('manufacturer'),
    active: integer('active', { mode: 'boolean' }).default(true)
});

export const qcDefinitions = sqliteTable('qc_definitions', {
    id: text('id').primaryKey(),
    materialId: text('material_id').notNull().references(() => qcMaterials.id),
    testCode: text('test_code').notNull(),
    testName: text('test_name').notNull(),
    mean: real('mean').notNull(),
    sd: real('sd').notNull(),
    unit: text('unit').notNull()
});

export const qcRuns = sqliteTable('qc_runs', {
    id: text('id').primaryKey(),
    definitionId: text('definition_id').notNull().references(() => qcDefinitions.id),
    value: real('value').notNull(),
    resultFlags: text('result_flags'), // JSON: ["1-2s", "1-3s"] etc
    status: text('status').notNull(), // Pass, Fail, Warning
    performedBy: text('performed_by').notNull(),
    timestamp: text('timestamp').notNull(),
    comments: text('comments')
});

// === EQUIPMENT ===
export const equipment = sqliteTable('equipment', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    type: text('type').notNull(),
    serialNumber: text('serial_number'),
    manufacturer: text('manufacturer'),
    department: text('department'),
    status: text('status').notNull().default('Active'), // Active, Maintenance, Retired
    lastServiceDate: text('last_service_date'),
    nextServiceDate: text('next_service_date'),
    active: integer('active', { mode: 'boolean' }).default(true)
});

export const equipmentLogs = sqliteTable('equipment_logs', {
    id: text('id').primaryKey(),
    equipmentId: text('equipment_id').notNull().references(() => equipment.id),
    type: text('type').notNull(), // Maintenance, Calibration, Error, Repair
    description: text('description').notNull(),
    performedBy: text('performed_by').notNull(),
    timestamp: text('timestamp').notNull(),
    outcome: text('outcome')
});

// === SYSTEM: LOCKS ===
export const recordLocks = sqliteTable('record_locks', {
    id: text('id').primaryKey(),
    entityType: text('entity_type').notNull(), // order, result, patient
    entityId: text('entity_id').notNull(),
    userId: text('user_id').notNull(),
    username: text('username').notNull(),
    timestamp: text('timestamp').notNull(),
    expiresAt: integer('expires_at').notNull()
});

// === COMMUNICATION ===
export const messages = sqliteTable('messages', {
    id: text('id').primaryKey(),
    sender: text('sender').notNull(),
    recipient: text('recipient'), // Null for broadcast? Or specific user/dept
    subject: text('subject').notNull(),
    body: text('body').notNull(),
    read: integer('read', { mode: 'boolean' }).default(false),
    timestamp: text('timestamp').notNull(),
    relatedEntityId: text('related_entity_id'),
    relatedEntityType: text('related_entity_type')
});

export const feedback = sqliteTable('feedback', {
    id: text('id').primaryKey(),
    userId: text('user_id').notNull(),
    type: text('type').notNull(), // Bug, Feature, General
    message: text('message').notNull(),
    status: text('status').default('New'), // New, Reviewed, Closed
    timestamp: text('timestamp').notNull()
});

export const documents = sqliteTable('documents', {
    id: text('id').primaryKey(),
    title: text('title').notNull(),
    category: text('category').notNull(), // SOP, Policy, Manual
    version: text('version').notNull(),
    status: text('status').notNull(), // Draft, Active, Archived
    filePath: text('file_path').notNull(),
    uploadedBy: text('uploaded_by'),
    uploadedAt: text('uploaded_at'),
    effectiveDate: text('effective_date')
});

// === REPORTING ===
export const emailQueue = sqliteTable('email_queue', {
    id: text('id').primaryKey(),
    recipient: text('recipient').notNull(),
    subject: text('subject').notNull(),
    body: text('body'), // HTML content
    attachmentPath: text('attachment_path'),
    status: text('status').default('Pending'), // Pending, Sent, Failed
    attempts: integer('attempts').default(0),
    createdAt: text('created_at').notNull(),
    sentAt: text('sent_at'),
    error: text('error')
});

// === SPECIALTY MODULES ===
// Histology
export const histoBlocks = sqliteTable('histo_blocks', {
    id: text('id').primaryKey(),
    specimenId: text('specimen_id').notNull().references(() => specimens.id),
    blockId: text('block_id').notNull().unique(), // Accession-A, Accession-B
    tissueType: text('tissue_type'),
    status: text('status').notNull(), // Cassette Printed, Embedded, Sectioned
    timestamp: text('timestamp')
});

export const histoSlides = sqliteTable('histo_slides', {
    id: text('id').primaryKey(),
    blockId: text('block_id').notNull().references(() => histoBlocks.id),
    slideId: text('slide_id').notNull().unique(),
    stain: text('stain').notNull(), // H&E, PAS, etc
    status: text('status').notNull(), // Printed, Stained, Cover-slipped, Released
    timestamp: text('timestamp')
});

// Microbiology
export const microCultures = sqliteTable('micro_cultures', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull().references(() => orders.id),
    specimenId: text('specimen_id').notNull().references(() => specimens.id),
    testId: text('test_id').notNull(),
    status: text('status').notNull(), // Setup, Incubation, Reading, Final
    incubatorLocation: text('incubator_location'),
    setupTime: text('setup_time'),
    preliminaryResult: text('preliminary_result'), // JSON: Gram stain etc
    finalResult: text('final_result') // JSON: Organism ID + AST
});

export const antibiotics = sqliteTable('antibiotics', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    code: text('code').unique(),
    class: text('class'),
    active: integer('active', { mode: 'boolean' }).default(true)
});

// Manufacturing
export const recipes = sqliteTable('recipes', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    description: text('description'),
    ingredients: text('ingredients'), // JSON list
    instructions: text('instructions'),
    yield: text('yield'), // e.g. "100 Plates"
    active: integer('active', { mode: 'boolean' }).default(true)
});

export const productionRuns = sqliteTable('production_runs', {
    id: text('id').primaryKey(),
    recipeId: text('recipe_id').notNull().references(() => recipes.id),
    batchNumber: text('batch_number').notNull().unique(),
    status: text('status').notNull(), // Scheduled, In Progress, QCorantine, Released, Failed
    quantity: integer('quantity').notNull(),
    startDate: text('start_date'),
    completionDate: text('completion_date'),
    expiryDate: text('expiry_date'),
    operator: text('operator')
});

// === SYSTEM: CONFIGURATION (Legacy Support) ===
export const settings = sqliteTable('settings', {
    id: text('id').primaryKey(),
    key: text('key').notNull().unique(),
    value: text('value').notNull() // JSON stringified value
});

export const worksheets = sqliteTable('worksheets', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    department: text('department').notNull(),
    testIds: text('test_ids'), // JSON array
    status: text('status'),
    createdAt: text('created_at'),
    createdBy: text('created_by')
});

export const workstations = sqliteTable('workstations', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    department: text('department').notNull(),
    ipAddress: text('ip_address'),
    printerId: text('printer_id'),
    instrumentIds: text('instrument_ids'), // JSON array
    active: integer('active', { mode: 'boolean' }).default(true)
});

export const routingRules = sqliteTable('routing_rules', {
    id: text('id').primaryKey(),
    testId: text('test_id').notNull(),
    workstationId: text('workstation_id'),
    departmentId: text('department_id'),
    conditions: text('conditions'), // JSON logic
    priority: integer('priority').default(0),
    active: integer('active', { mode: 'boolean' }).default(true)
});

export const routingAssignments = sqliteTable('routing_assignments', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull().references(() => orders.id),
    testId: text('test_id').notNull(),
    workstationId: text('workstation_id').notNull().references(() => workstations.id),
    status: text('status').notNull(), // Pending, In Progress, Completed
    timestamp: text('timestamp').notNull()
});

// === CLINICAL ENGINE ===

export const deltaCheckRules = sqliteTable('delta_check_rules', {
    id: text('id').primaryKey(),
    testId: text('test_id').notNull(),
    testCode: text('test_code').notNull(),
    deltaType: text('delta_type').notNull(), // 'percent' | 'absolute'
    threshold: real('threshold').notNull(),
    direction: text('direction').notNull().default('any'), // 'any' | 'increase' | 'decrease'
    enabled: integer('enabled', { mode: 'boolean' }).default(true),
    createdAt: text('created_at').notNull(),
    createdBy: text('created_by')
});

export const deltaCheckFlags = sqliteTable('delta_check_flags', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull(),
    testId: text('test_id').notNull(),
    ruleId: text('rule_id').notNull(),
    previousOrderId: text('previous_order_id'),
    previousValue: real('previous_value'),
    currentValue: real('current_value').notNull(),
    deltaPercent: real('delta_percent'),
    deltaAbsolute: real('delta_absolute'),
    flaggedAt: text('flagged_at').notNull(),
    acknowledgedBy: text('acknowledged_by'),
    acknowledgedAt: text('acknowledged_at')
});

export const criticalValueNotifications = sqliteTable('critical_value_notifications', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull(),
    patientId: text('patient_id').notNull(),
    testId: text('test_id').notNull(),
    testCode: text('test_code').notNull(),
    value: text('value').notNull(),
    threshold: text('threshold').notNull(),
    criticalType: text('critical_type').notNull(), // 'HIGH' | 'LOW'
    status: text('status').notNull().default('Pending'), // Pending, Acknowledged, Escalated
    createdAt: text('created_at').notNull(),
    createdBy: text('created_by')
});

export const criticalValueAcknowledgments = sqliteTable('critical_value_acknowledgments', {
    id: text('id').primaryKey(),
    notificationId: text('notification_id').notNull(),
    acknowledgedBy: text('acknowledged_by').notNull(),
    acknowledgedAt: text('acknowledged_at').notNull(),
    notifiedClinician: text('notified_clinician'),
    notificationMethod: text('notification_method'), // phone, fax, in-person
    notes: text('notes'),
    escalatedTo: text('escalated_to')
});

export const reflexRules = sqliteTable('reflex_rules', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    triggerTestId: text('trigger_test_id').notNull(),
    triggerCondition: text('trigger_condition').notNull(), // JSON: { operator: '>', value: 5.0 }
    addTestId: text('add_test_id').notNull(),
    addTestCode: text('add_test_code').notNull(),
    enabled: integer('enabled', { mode: 'boolean' }).default(true),
    createdAt: text('created_at').notNull(),
    createdBy: text('created_by')
});

export const reflexActivations = sqliteTable('reflex_activations', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull(),
    ruleId: text('rule_id').notNull(),
    triggerValue: text('trigger_value').notNull(),
    newTestId: text('new_test_id').notNull(),
    triggeredAt: text('triggered_at').notNull(),
    status: text('status').notNull().default('Pending') // Pending, Ordered, Completed
});

export const resultSignatures = sqliteTable('result_signatures', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull(),
    signedBy: text('signed_by').notNull(),
    signedAt: text('signed_at').notNull(),
    signatureType: text('signature_type').notNull(), // 'technical' | 'clinical'
    ipAddress: text('ip_address'),
    userAgent: text('user_agent')
});

export const tatThresholds = sqliteTable('tat_thresholds', {
    id: text('id').primaryKey(),
    scope: text('scope').notNull(), // 'test' | 'department' | 'global'
    scopeId: text('scope_id'), // testCode, departmentCode, or null
    targetHours: real('target_hours').notNull(),
    warningHours: real('warning_hours').notNull(),
    breachHours: real('breach_hours').notNull(),
    priority: text('priority').default('Routine'),
    active: integer('active', { mode: 'boolean' }).default(true),
    createdAt: text('created_at').notNull()
});

export const tatBreaches = sqliteTable('tat_breaches', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull(),
    actualHours: real('actual_hours').notNull(),
    targetHours: real('target_hours').notNull(),
    breachType: text('breach_type').notNull(), // 'warning' | 'critical'
    detectedAt: text('detected_at').notNull(),
    resolvedAt: text('resolved_at'),
    notifiedAt: text('notified_at')
});

export const userCompetencies = sqliteTable('user_competencies', {
    id: text('id').primaryKey(),
    userId: text('user_id').notNull(),
    testId: text('test_id'),
    category: text('category'),
    competencyDate: text('competency_date').notNull(),
    expiryDate: text('expiry_date').notNull(),
    assessedBy: text('assessed_by').notNull(),
    status: text('status').notNull().default('Active'), // Active, Expired, Suspended
    notes: text('notes'),
    createdAt: text('created_at').notNull()
});

export const retentionPolicies = sqliteTable('retention_policies', {
    id: text('id').primaryKey(),
    specimenType: text('specimen_type').notNull(),
    retentionDays: integer('retention_days').notNull(),
    temperature: text('temperature'),
    disposalMethod: text('disposal_method').notNull().default('Biohazard Disposal'),
    active: integer('active', { mode: 'boolean' }).default(true),
    notes: text('notes'),
    createdAt: text('created_at').notNull()
});

export const specimenDisposals = sqliteTable('specimen_disposals', {
    id: text('id').primaryKey(),
    specimenId: text('specimen_id').notNull(),
    policyId: text('policy_id'),
    disposedAt: text('disposed_at').notNull(),
    disposedBy: text('disposed_by').notNull(),
    batchNumber: text('batch_number'),
    notes: text('notes')
});

export const requesters = sqliteTable('requesters', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    type: text('type').notNull(), // GP | Ward | Clinic | Hospital | External
    contactName: text('contact_name'),
    email: text('email'),
    phone: text('phone'),
    fax: text('fax'),
    address: text('address'),
    deliveryPreference: text('delivery_preference').default('portal'), // portal | email | print | fax
    active: integer('active', { mode: 'boolean' }).default(true),
    createdAt: text('created_at').notNull(),
    notes: text('notes')
});

export const distributionRules = sqliteTable('distribution_rules', {
    id: text('id').primaryKey(),
    requesterId: text('requester_id'),
    testId: text('test_id'),
    method: text('method').notNull(), // email | print | fax | portal
    destination: text('destination'),
    autoRelease: integer('auto_release', { mode: 'boolean' }).default(false),
    active: integer('active', { mode: 'boolean' }).default(true),
    createdAt: text('created_at').notNull()
});

export const distributionLogs = sqliteTable('distribution_logs', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull(),
    ruleId: text('rule_id'),
    method: text('method').notNull(),
    destination: text('destination'),
    sentAt: text('sent_at'),
    status: text('status').notNull().default('Pending'), // Pending | Sent | Failed
    error: text('error')
});

export const notifiableConditions = sqliteTable('notifiable_conditions', {
    id: text('id').primaryKey(),
    name: text('name').notNull(),
    organism: text('organism'),
    testIds: text('test_ids'), // JSON array
    reportingBody: text('reporting_body').notNull(),
    timeframe: text('timeframe').notNull().default('24h'),
    active: integer('active', { mode: 'boolean' }).default(true),
    createdAt: text('created_at').notNull()
});

export const epidemiologyNotifications = sqliteTable('epidemiology_notifications', {
    id: text('id').primaryKey(),
    orderId: text('order_id').notNull(),
    patientId: text('patient_id').notNull(),
    conditionId: text('condition_id').notNull(),
    detectedAt: text('detected_at').notNull(),
    status: text('status').notNull().default('Pending'), // Pending | Reviewed | Submitted | Closed
    reviewedBy: text('reviewed_by'),
    reviewedAt: text('reviewed_at'),
    submittedBy: text('submitted_by'),
    submittedAt: text('submitted_at'),
    notes: text('notes')
});

export const phlebotomySchedules = sqliteTable('phlebotomy_schedules', {
    id: text('id').primaryKey(),
    patientId: text('patient_id').notNull(),
    orderId: text('order_id'),
    wardLocation: text('ward_location').notNull(),
    scheduledAt: text('scheduled_at').notNull(),
    collectionType: text('collection_type').notNull().default('Routine'), // Routine | STAT | Timed
    testIds: text('test_ids'), // JSON array
    assignedTo: text('assigned_to'),
    status: text('status').notNull().default('Scheduled'), // Scheduled | InProgress | Completed | Cancelled
    notes: text('notes'),
    completedAt: text('completed_at'),
    createdAt: text('created_at').notNull()
});

export const loincCodes = sqliteTable('loinc_codes', {
    id: text('id').primaryKey(),
    loincCode: text('loinc_code').notNull().unique(),
    longName: text('long_name').notNull(),
    shortName: text('short_name'),
    component: text('component'),
    property: text('property'),
    timeAspect: text('time_aspect'),
    system: text('system'),
    scale: text('scale'), // Qn, Ord, Nom
    method: text('method'),
    status: text('status').default('Active')
});

export const specimenReceiving = sqliteTable('specimen_receiving', {
    id: text('id').primaryKey(),
    specimenId: text('specimen_id').notNull(),
    orderId: text('order_id').notNull(),
    receivedAt: text('received_at').notNull(),
    receivedBy: text('received_by').notNull(),
    condition: text('condition').notNull().default('Acceptable'), // Acceptable | Rejected | Marginal
    conditionNotes: text('condition_notes'),
    rejectionReason: text('rejection_reason'),
    temperature: text('temperature'),
    volume: real('volume'),
    status: text('status').notNull().default('Accepted') // Accepted | Rejected | Recollection-Required
});

export const demographicReferenceRanges = sqliteTable('demographic_reference_ranges', {
    id: text('id').primaryKey(),
    testId: text('test_id').notNull(),
    testCode: text('test_code').notNull(),
    ageMin: integer('age_min'),
    ageMax: integer('age_max'),
    gender: text('gender').default('All'), // M | F | All
    pregnancy: integer('pregnancy', { mode: 'boolean' }).default(false),
    trimester: integer('trimester'),
    lowNormal: real('low_normal'),
    highNormal: real('high_normal'),
    lowCritical: real('low_critical'),
    highCritical: real('high_critical'),
    unit: text('unit'),
    notes: text('notes'),
    active: integer('active', { mode: 'boolean' }).default(true),
    createdAt: text('created_at').notNull()
});

export const calculatedTests = sqliteTable('calculated_tests', {
    id: text('id').primaryKey(),
    testCode: text('test_code').notNull().unique(), // eGFR, LDL, AGAP, etc.
    name: text('name').notNull(),
    formula: text('formula').notNull(), // JSON: { type: 'ckd_epi', inputs: [...] }
    unit: text('unit'),
    active: integer('active', { mode: 'boolean' }).default(true),
    createdAt: text('created_at').notNull()
});


