
import { db } from '@/db';
import {
    users, patients, orders, results, testDefinitions,
    systemAlerts, auditLogs, specimens, authorizationQueues,
    billingItems, invoices, inventoryItems, inventoryTransactions,
    departments, rejectionCriteria, qcMaterials, qcDefinitions, qcRuns,
    equipment, equipmentLogs, recordLocks, messages, feedback, documents,
    emailQueue, histoBlocks, histoSlides, microCultures, antibiotics,
    recipes, productionRuns, settings, worksheets, workstations,
    routingRules, routingAssignments
} from '@/db/schema';
import { eq } from 'drizzle-orm';
import { fuzzyMatch, generateZPLLabel, evaluateResult } from './utils';
import { v4 as uuidv4 } from 'uuid';

export { fuzzyMatch, generateZPLLabel, evaluateResult };

// First param kept for caller compatibility; audit rows always go through Drizzle
// (callers variously pass the readDb() JSON object, which has no .insert).
export async function logAudit(_dbIgnored: any, entityType: string, entityId: string, action: string, previousData: any, newData: any, userId: string) {
    try {
        await db.insert(auditLogs).values({
            id: uuidv4(),
            entityType,
            entityId,
            action,
            userId,
            timestamp: new Date().toISOString(),
            details: JSON.stringify({ previous: previousData, new: newData })
        });
    } catch (e) {
        console.error('Failed to log audit:', e);
    }
}


export async function readDb(): Promise<any> {
    try {
        // Fetch core data from SQLite
        const [
            usersData,
            patientsData,
            ordersData,
            resultsData,
            specimensData,
            testsData,
            alertsData,
            queuesData,
            auditLogsData,
            rejectionCriteriaData,
            qcMaterialsData,
            qcDefinitionsData,
            qcRunsData,
            equipmentData,
            equipmentLogsData,
            recordLocksData,
            messagesData,
            feedbackData,
            documentsData,
            emailQueueData,
            histoBlocksData,
            histoSlidesData,
            microCulturesData,
            antibioticsData,
            recipesData,
            productionRunsData,
            settingsData,
            worksheetsData,
            workstationsData,
            routingRulesData,
            routingAssignmentsData,
            inventoryItemsData,
            inventoryTransactionsData,
            billingItemsData,
            invoicesData
        ] = await Promise.all([
            db.select().from(users),
            db.select().from(patients),
            db.select().from(orders),
            db.select().from(results),
            db.select().from(specimens),
            db.select().from(testDefinitions),
            db.select().from(systemAlerts),
            db.select().from(authorizationQueues),
            db.select().from(auditLogs),
            db.select().from(rejectionCriteria),
            db.select().from(qcMaterials),
            db.select().from(qcDefinitions),
            db.select().from(qcRuns),
            db.select().from(equipment),
            db.select().from(equipmentLogs),
            db.select().from(recordLocks),
            db.select().from(messages),
            db.select().from(feedback),
            db.select().from(documents),
            db.select().from(emailQueue),
            db.select().from(histoBlocks),
            db.select().from(histoSlides),
            db.select().from(microCultures),
            db.select().from(antibiotics),
            db.select().from(recipes),
            db.select().from(productionRuns),
            db.select().from(settings),
            db.select().from(worksheets),
            db.select().from(workstations),
            db.select().from(routingRules),
            db.select().from(routingAssignments),
            db.select().from(inventoryItems),
            db.select().from(inventoryTransactions),
            db.select().from(billingItems),
            db.select().from(invoices)
        ]);

        // Fetch departments separately (table might not exist in older DBs)
        let departmentsData: any[] = [];
        try {
            departmentsData = await db.select().from(departments);
        } catch (e) {
            console.warn('Departments table not found, returning empty array');
        }

        // Transform flat SQL rows back to complex objects if needed
        // (e.g. JSON parsing for testIds, readBy, etc.)

        const parseJson = (val: string | null) => {
            if (!val) return null;
            try {
                return JSON.parse(val);
            } catch (e) {
                console.warn('Failed to parse JSON field:', val);
                return null;
            }
        };

        return {
            users: usersData,
            patients: patientsData,
            orders: ordersData.map(o => ({
                ...o,
                testIds: parseJson(o.testIds) || [],
                // Ensure other fields match expected type
            })),
            results: resultsData.map(r => ({
                ...r,
                values: parseJson(r.values) || {},
                resultFlags: parseJson(r.resultFlags) || []
            })),
            specimens: specimensData,
            testDefinitions: testsData.map(t => ({
                ...t,
                referenceRange: parseJson(t.referenceRange),
                specimenTypes: parseJson(t.specimenTypes) || []
            })),
            systemAlerts: alertsData.map(a => ({
                ...a,
                readBy: parseJson(a.readBy) || []
            })),
            authorizationQueues: queuesData.map(q => ({
                ...q,
                allowedRoles: parseJson(q.allowedRoles) || []
            })),

            // Empty defaults for unmigrated collections
            // Or access directly via db if needed
            auditLogs: auditLogsData,
            departments: departmentsData,
            rejectionCriteria: rejectionCriteriaData,
            qcMaterials: qcMaterialsData,
            qcDefinitions: qcDefinitionsData,
            qcRuns: qcRunsData.map(r => ({
                ...r,
                resultFlags: parseJson(r.resultFlags)
            })),
            equipment: equipmentData,
            equipmentLogs: equipmentLogsData,
            recordLocks: recordLocksData,
            messages: messagesData,
            feedback: feedbackData,
            documents: documentsData,
            emailQueue: emailQueueData,
            histoBlocks: histoBlocksData,
            histoSlides: histoSlidesData,
            microCultures: microCulturesData.map(m => ({
                ...m,
                preliminaryResult: parseJson(m.preliminaryResult),
                finalResult: parseJson(m.finalResult)
            })),
            antibiotics: antibioticsData,
            recipes: recipesData.map(r => ({
                ...r,
                ingredients: parseJson(r.ingredients)
            })),
            productionRuns: productionRunsData,

            // === Polyfills for Legacy API Compatibility ===
            inventory: inventoryItemsData,

            settings: settingsData.reduce<Record<string, any>>((acc, curr) => ({ ...acc, [curr.key]: parseJson(curr.value) }), {}),

            // === Virtual Tables (Stored in Settings) ===
            specimenTypes: parseJson(settingsData.find(s => s.key === 'specimenTypes')?.value || null) || [],
            commentCodes: parseJson(settingsData.find(s => s.key === 'commentCodes')?.value || null) || [],
            manualSections: parseJson(settingsData.find(s => s.key === 'manualSections')?.value || null) || [], // Fixed null/undefined issue
            storageLocations: parseJson(settingsData.find(s => s.key === 'storageLocations')?.value || null) || [],
            cocEvents: parseJson(settingsData.find(s => s.key === 'cocEvents')?.value || null) || [],
            orderPayments: parseJson(settingsData.find(s => s.key === 'orderPayments')?.value || null) || {},

            worksheets: worksheetsData.map(w => ({
                ...w,
                testIds: parseJson(w.testIds) || []
            })),
            workstations: workstationsData.map(w => ({
                ...w,
                instrumentIds: parseJson(w.instrumentIds) || []
            })),
            routingRules: routingRulesData.map(r => ({
                ...r,
                conditions: parseJson(r.conditions) || {}
            })),
            routingAssignments: routingAssignmentsData,

            billingItems: billingItemsData,
            invoices: invoicesData,
            // MAPPING: inventoryItems -> inventory
            inventoryItems: inventoryItemsData,
            inventoryTransactions: inventoryTransactionsData
        };

    } catch (error) {
        console.error('Error reading DB:', error);
        throw error;
    }
}

export async function writeDb(data: any) {
    // Naive "Sync" - implementation for backward compatibility
    // In a real refactor, we would change API routes to not use writeDb(fullObject).

    // For now, we assume the caller modified some objects in the arrays and wants to save them.
    // We will attempt to Upsert them.

    try {
        // 1. Users
        if (data.users?.length) {
            for (const u of data.users) {
                await db.insert(users).values(u).onConflictDoUpdate({ target: users.id, set: u });
            }
        }

        // 1b. Patients
        if (data.patients?.length) {
            for (const p of data.patients) {
                await db.insert(patients).values(p).onConflictDoUpdate({ target: patients.id, set: p });
            }
        }

        // 1c. Test Definitions
        if (data.testDefinitions?.length) {
            for (const t of data.testDefinitions) {
                const row = {
                    ...t,
                    referenceRange: JSON.stringify(t.referenceRange),
                    specimenTypes: JSON.stringify(t.specimenTypes)
                };
                await db.insert(testDefinitions).values(row).onConflictDoUpdate({ target: testDefinitions.id, set: row });
            }
        }

        // 2. Orders
        if (data.orders?.length) {
            for (const o of data.orders) {
                const row = {
                    ...o,
                    testIds: JSON.stringify(o.testIds)
                };
                await db.insert(orders).values(row).onConflictDoUpdate({ target: orders.id, set: row });
            }
        }

        // 3. Results
        if (data.results?.length) {
            for (const r of data.results) {
                const row = {
                    ...r,
                    values: JSON.stringify(r.values),
                    resultFlags: JSON.stringify(r.resultFlags)
                };
                await db.insert(results).values(row).onConflictDoUpdate({ target: results.id, set: row });
            }
        }

        // 4. Alerts
        if (data.systemAlerts?.length) {
            for (const a of data.systemAlerts) {
                const row = {
                    ...a,
                    readBy: JSON.stringify(a.readBy)
                };
                await db.insert(systemAlerts).values(row).onConflictDoUpdate({ target: systemAlerts.id, set: row });
            }
        }

        // 5. Queues
        if (data.authorizationQueues?.length) {
            for (const q of data.authorizationQueues) {
                const row = {
                    ...q,
                    allowedRoles: JSON.stringify(q.allowedRoles)
                };
                await db.insert(authorizationQueues).values(row).onConflictDoUpdate({ target: authorizationQueues.id, set: row });
            }
        }

        // 6. Departments
        if (data.departments?.length) {
            for (const d of data.departments) {
                await db.insert(departments).values(d).onConflictDoUpdate({ target: departments.id, set: d });
            }
        }

        if (data.settings) {
            // Convert object back to array of rows
            for (const [key, value] of Object.entries(data.settings)) {
                const row = { id: key, key, value: JSON.stringify(value) };
                await db.insert(settings).values(row).onConflictDoUpdate({ target: settings.key, set: row });
            }
        }

        // === Virtual Tables (Save to Settings) ===
        const virtualSettings = ['specimenTypes', 'commentCodes', 'manualSections', 'storageLocations', 'cocEvents', 'orderPayments'];
        for (const key of virtualSettings) {
            if (data[key]) {
                const row = { id: key, key, value: JSON.stringify(data[key]) };
                await db.insert(settings).values(row).onConflictDoUpdate({ target: settings.key, set: row });
            }
        }

        // 7. Generic handler for simple tables
        const simpleTables = [
            { name: 'rejectionCriteria', schema: rejectionCriteria },
            { name: 'qcMaterials', schema: qcMaterials },
            { name: 'qcDefinitions', schema: qcDefinitions },
            { name: 'equipment', schema: equipment },
            { name: 'equipmentLogs', schema: equipmentLogs },
            { name: 'recordLocks', schema: recordLocks },
            { name: 'messages', schema: messages },
            { name: 'feedback', schema: feedback },
            { name: 'documents', schema: documents },
            { name: 'emailQueue', schema: emailQueue },
            { name: 'histoBlocks', schema: histoBlocks },
            { name: 'histoSlides', schema: histoSlides },
            { name: 'antibiotics', schema: antibiotics },
            { name: 'productionRuns', schema: productionRuns },
            // { name: 'worksheets', schema: worksheets }, // Has JSON
            // { name: 'workstations', schema: workstations }, // Has JSON
            // { name: 'routingRules', schema: routingRules }, // Has JSON
            { name: 'routingAssignments', schema: routingAssignments },
            { name: 'inventoryItems', schema: inventoryItems },
            { name: 'inventoryTransactions', schema: inventoryTransactions }
        ];

        for (const tbl of simpleTables) {
            if (data[tbl.name]?.length) {
                for (const item of data[tbl.name]) {
                    // Filter out any undefined keys to avoid SQL errors
                    // const cleanItem = Object.fromEntries(Object.entries(item).filter(([_, v]) => v !== undefined));
                    await db.insert(tbl.schema).values(item).onConflictDoUpdate({ target: tbl.schema.id, set: item });
                }
            }
        }

        // 8. Complex tables with JSON fields
        if (data.qcRuns?.length) {
            for (const r of data.qcRuns) {
                const row = {
                    ...r,
                    resultFlags: JSON.stringify(r.resultFlags)
                };
                await db.insert(qcRuns).values(row).onConflictDoUpdate({ target: qcRuns.id, set: row });
            }
        }

        if (data.microCultures?.length) {
            for (const m of data.microCultures) {
                const row = {
                    ...m,
                    preliminaryResult: JSON.stringify(m.preliminaryResult),
                    finalResult: JSON.stringify(m.finalResult)
                };
                await db.insert(microCultures).values(row).onConflictDoUpdate({ target: microCultures.id, set: row });
            }
        }

        if (data.recipes?.length) {
            for (const r of data.recipes) {
                const row = {
                    ...r,
                    ingredients: JSON.stringify(r.ingredients)
                };
                await db.insert(recipes).values(row).onConflictDoUpdate({ target: recipes.id, set: row });
            }
        }

        if (data.worksheets?.length) {
            for (const w of data.worksheets) {
                const row = { ...w, testIds: JSON.stringify(w.testIds) };
                await db.insert(worksheets).values(row).onConflictDoUpdate({ target: worksheets.id, set: row });
            }
        }

        if (data.workstations?.length) {
            for (const w of data.workstations) {
                const row = { ...w, instrumentIds: JSON.stringify(w.instrumentIds) };
                await db.insert(workstations).values(row).onConflictDoUpdate({ target: workstations.id, set: row });
            }
        }

        if (data.routingRules?.length) {
            for (const r of data.routingRules) {
                const row = { ...r, conditions: JSON.stringify(r.conditions) };
                await db.insert(routingRules).values(row).onConflictDoUpdate({ target: routingRules.id, set: row });
            }
        }

        // ... handled other tables similarly if needed

    } catch (error) {
        console.error('Error writing DB:', error);
    }
}
