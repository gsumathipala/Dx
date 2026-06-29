import { db } from '@/db';
import {
    deltaCheckRules, deltaCheckFlags,
    criticalValueNotifications,
    reflexRules, reflexActivations,
    results, orders, testDefinitions,
    demographicReferenceRanges,
    notifiableConditions, epidemiologyNotifications
} from '@/db/schema';
import { eq, and, desc, ne } from 'drizzle-orm';
import { v4 as uuidv4 } from 'uuid';

// ─── Delta Checks ───────────────────────────────────────────────────────────

export async function runDeltaChecks(
    orderId: string,
    patientId: string,
    testId: string,
    currentValue: number
): Promise<{ flagged: boolean; flags: any[] }> {
    const flags: any[] = [];
    try {
        const rules = await db.select().from(deltaCheckRules)
            .where(and(eq(deltaCheckRules.testId, testId), eq(deltaCheckRules.enabled, true)));
        if (rules.length === 0) return { flagged: false, flags };

        // Find previous result for this patient/test
        const prevOrders = await db.select({ id: orders.id })
            .from(orders)
            .where(and(eq(orders.patientId, patientId), ne(orders.id, orderId)))
            .orderBy(desc(orders.timestamp))
            .limit(5);

        if (prevOrders.length === 0) return { flagged: false, flags };

        let prevResult: { value: number; orderId: string } | null = null;
        for (const prevOrder of prevOrders) {
            const rows = await db.select().from(results)
                .where(and(eq(results.orderId, prevOrder.id), eq(results.testId, testId)))
                .limit(1);
            if (rows.length > 0) {
                try {
                    const parsed = JSON.parse(rows[0].values || '{}');
                    const val = parseFloat(parsed.value);
                    if (!isNaN(val)) {
                        prevResult = { value: val, orderId: prevOrder.id };
                        break;
                    }
                } catch { /* skip */ }
            }
        }

        if (!prevResult) return { flagged: false, flags };

        for (const rule of rules) {
            const deltaAbs = Math.abs(currentValue - prevResult.value);
            const deltaPct = prevResult.value !== 0
                ? Math.abs((currentValue - prevResult.value) / prevResult.value) * 100
                : 0;

            const directionChange = currentValue > prevResult.value ? 'increase' : 'decrease';
            const directionOk = rule.direction === 'any' || rule.direction === directionChange;
            if (!directionOk) continue;

            let exceeded = false;
            if (rule.deltaType === 'percent' && deltaPct >= rule.threshold) exceeded = true;
            if (rule.deltaType === 'absolute' && deltaAbs >= rule.threshold) exceeded = true;

            if (exceeded) {
                const flag = {
                    id: uuidv4(),
                    orderId,
                    testId,
                    ruleId: rule.id,
                    previousOrderId: prevResult.orderId,
                    previousValue: prevResult.value,
                    currentValue,
                    deltaPercent: deltaPct,
                    deltaAbsolute: deltaAbs,
                    flaggedAt: new Date().toISOString()
                };
                await db.insert(deltaCheckFlags).values(flag);
                flags.push(flag);
            }
        }

        return { flagged: flags.length > 0, flags };
    } catch (e) {
        console.error('Delta check error:', e);
        return { flagged: false, flags };
    }
}

// ─── Critical Value Detection ────────────────────────────────────────────────

export async function checkCriticalValues(
    orderId: string,
    patientId: string,
    testId: string,
    testCode: string,
    value: number,
    enteredBy: string
): Promise<boolean> {
    try {
        // Check test definition for critical range in referenceRange JSON
        const testDefs = await db.select().from(testDefinitions)
            .where(eq(testDefinitions.id, testId)).limit(1);
        if (testDefs.length === 0) return false;

        const refRange = (() => {
            try { return JSON.parse(testDefs[0].referenceRange || 'null'); } catch { return null; }
        })();

        if (!refRange) return false;

        let isCritical = false;
        let criticalType: 'HIGH' | 'LOW' = 'HIGH';
        let threshold = '';

        // Canonical shape is { min, max, panicLow, panicHigh }; accept criticalLow/High as aliases
        const critLow = typeof refRange.panicLow === 'number' ? refRange.panicLow : refRange.criticalLow;
        const critHigh = typeof refRange.panicHigh === 'number' ? refRange.panicHigh : refRange.criticalHigh;

        if (typeof critLow === 'number' && value < critLow) {
            isCritical = true;
            criticalType = 'LOW';
            threshold = `< ${critLow} ${testDefs[0].units || ''}`.trim();
        } else if (typeof critHigh === 'number' && value > critHigh) {
            isCritical = true;
            criticalType = 'HIGH';
            threshold = `> ${critHigh} ${testDefs[0].units || ''}`.trim();
        }

        if (!isCritical) return false;

        await db.insert(criticalValueNotifications).values({
            id: uuidv4(),
            orderId,
            patientId,
            testId,
            testCode,
            value: String(value),
            threshold,
            criticalType,
            status: 'Pending',
            createdAt: new Date().toISOString(),
            createdBy: enteredBy
        });

        return true;
    } catch (e) {
        console.error('Critical value check error:', e);
        return false;
    }
}

// ─── Reflex Testing ──────────────────────────────────────────────────────────

export async function evaluateReflexRules(
    orderId: string,
    testId: string,
    value: number
): Promise<string[]> {
    const addedTestIds: string[] = [];
    try {
        const rules = await db.select().from(reflexRules)
            .where(and(eq(reflexRules.triggerTestId, testId), eq(reflexRules.enabled, true)));

        for (const rule of rules) {
            let condition: { operator: string; value: number };
            try { condition = JSON.parse(rule.triggerCondition); } catch { continue; }

            let triggered = false;
            switch (condition.operator) {
                case '>':  triggered = value > condition.value; break;
                case '>=': triggered = value >= condition.value; break;
                case '<':  triggered = value < condition.value; break;
                case '<=': triggered = value <= condition.value; break;
                case '==': triggered = value === condition.value; break;
                default: break;
            }

            if (triggered) {
                // Check not already activated for this order
                const existing = await db.select().from(reflexActivations)
                    .where(and(eq(reflexActivations.orderId, orderId), eq(reflexActivations.ruleId, rule.id)))
                    .limit(1);
                if (existing.length === 0) {
                    await db.insert(reflexActivations).values({
                        id: uuidv4(),
                        orderId,
                        ruleId: rule.id,
                        triggerValue: String(value),
                        newTestId: rule.addTestId,
                        triggeredAt: new Date().toISOString(),
                        status: 'Pending'
                    });

                    // Append the reflexed test to the order so it appears in results entry
                    const orderRows = await db.select().from(orders).where(eq(orders.id, orderId)).limit(1);
                    if (orderRows.length > 0) {
                        let testIds: string[] = [];
                        try { testIds = JSON.parse(orderRows[0].testIds || '[]'); } catch { /* keep empty */ }
                        if (!testIds.includes(rule.addTestId)) {
                            testIds.push(rule.addTestId);
                            await db.update(orders)
                                .set({ testIds: JSON.stringify(testIds), updatedAt: new Date().toISOString() })
                                .where(eq(orders.id, orderId));
                        }
                    }

                    addedTestIds.push(rule.addTestId);
                }
            }
        }
        return addedTestIds;
    } catch (e) {
        console.error('Reflex rule error:', e);
        return [];
    }
}

// ─── Notifiable Condition Detection (Epidemiology) ──────────────────────────

export async function checkNotifiableConditions(
    orderId: string,
    patientId: string,
    testId: string
): Promise<boolean> {
    try {
        const conditions = await db.select().from(notifiableConditions)
            .where(eq(notifiableConditions.active, true));

        for (const condition of conditions) {
            let linkedTestIds: string[] = [];
            try { linkedTestIds = JSON.parse(condition.testIds || '[]'); } catch { continue; }
            if (!linkedTestIds.includes(testId)) continue;

            // Avoid duplicate notifications for the same order/condition
            const existing = await db.select().from(epidemiologyNotifications)
                .where(and(
                    eq(epidemiologyNotifications.orderId, orderId),
                    eq(epidemiologyNotifications.conditionId, condition.id)
                )).limit(1);
            if (existing.length > 0) continue;

            await db.insert(epidemiologyNotifications).values({
                id: uuidv4(),
                orderId,
                patientId,
                conditionId: condition.id,
                detectedAt: new Date().toISOString(),
                status: 'Pending'
            });
            return true;
        }
        return false;
    } catch (e) {
        console.error('Notifiable condition check error:', e);
        return false;
    }
}

// ─── Demographic Reference Range Lookup ─────────────────────────────────────

export async function getDemographicRefRange(
    testId: string,
    ageYears: number | null,
    gender: string | null,
    isPregnant = false,
    trimester?: number
): Promise<any | null> {
    try {
        const ranges = await db.select().from(demographicReferenceRanges)
            .where(and(
                eq(demographicReferenceRanges.testId, testId),
                eq(demographicReferenceRanges.active, true)
            ));

        // Score each range by specificity
        let bestMatch: any = null;
        let bestScore = -1;

        for (const range of ranges) {
            let score = 0;

            // Age matching
            if (ageYears !== null) {
                const ageOk =
                    (range.ageMin === null || ageYears >= range.ageMin) &&
                    (range.ageMax === null || ageYears <= range.ageMax);
                if (!ageOk) continue;
                if (range.ageMin !== null || range.ageMax !== null) score += 2;
            }

            // Gender matching
            if (gender && range.gender !== 'All') {
                if (range.gender !== gender) continue;
                score += 2;
            }

            // Pregnancy matching
            if (isPregnant && range.pregnancy) {
                score += 3;
                if (trimester && range.trimester === trimester) score += 2;
            } else if (!isPregnant && range.pregnancy) {
                continue; // don't use pregnancy range for non-pregnant
            }

            if (score > bestScore) {
                bestScore = score;
                bestMatch = range;
            }
        }

        return bestMatch;
    } catch (e) {
        console.error('Demographic range lookup error:', e);
        return null;
    }
}

// ─── Calculated Test Engine ──────────────────────────────────────────────────

interface ResultMap { [testCode: string]: number }

export function computeCalculatedTests(
    formulaType: string,
    inputs: ResultMap,
    patientAge?: number,
    patientGender?: string
): number | null {
    try {
        switch (formulaType) {
            case 'ldl_friedewald': {
                // LDL = TC - HDL - (TG / 2.2)  [mmol/L]
                const { TC, HDL, TG } = inputs;
                if (TC === undefined || HDL === undefined || TG === undefined) return null;
                if (TG > 4.5) return null; // Formula invalid when TG > 4.5 mmol/L
                return Math.round((TC - HDL - TG / 2.2) * 100) / 100;
            }
            case 'anion_gap': {
                // AG = Na - (Cl + HCO3)
                const { Na, Cl, HCO3 } = inputs;
                if (Na === undefined || Cl === undefined || HCO3 === undefined) return null;
                return Math.round((Na - (Cl + HCO3)) * 10) / 10;
            }
            case 'a_g_ratio': {
                // A:G = ALB / (TP - ALB)
                const { ALB, TP } = inputs;
                if (ALB === undefined || TP === undefined) return null;
                const globulin = TP - ALB;
                if (globulin <= 0) return null;
                return Math.round((ALB / globulin) * 100) / 100;
            }
            case 'egfr_ckd_epi': {
                // CKD-EPI 2021 creatinine equation (eGFR in mL/min/1.73m²)
                // Using CREA in µmol/L, age in years
                const { CREA } = inputs;
                if (CREA === undefined || patientAge === undefined || patientGender === undefined) return null;
                const crMgDl = CREA / 88.4; // convert µmol/L to mg/dL
                const isFemale = patientGender === 'F';
                const kappa = isFemale ? 0.7 : 0.9;
                const alpha = isFemale ? -0.241 : -0.302;
                const sex = isFemale ? 1.012 : 1.0;
                const ratio = crMgDl / kappa;
                const term1 = Math.min(ratio, 1) ** alpha;
                const term2 = Math.max(ratio, 1) ** (-1.200);
                const egfr = 142 * term1 * term2 * (0.9938 ** patientAge) * sex;
                return Math.round(egfr);
            }
            default:
                return null;
        }
    } catch {
        return null;
    }
}
