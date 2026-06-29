import { NextResponse } from 'next/server';
import { db } from '@/db';
import { calculatedTests, results, orders, patients } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { getAuthUser } from '@/lib/auth';

interface FormulaDefinition {
    type: string;
    inputs: string[];
    coefficients?: Record<string, number>;
}

function computeFormula(
    formula: FormulaDefinition,
    valueMap: Record<string, number>,
    patientInfo?: { age?: number; gender?: string }
): number | null {
    const get = (code: string): number | null => {
        const v = valueMap[code];
        return v != null ? v : null;
    };

    switch (formula.type) {
        case 'ldl_friedewald': {
            // LDL = TC - HDL - (TG / 2.2)
            const TC = get('TC');
            const HDL = get('HDL');
            const TG = get('TG');
            if (TC == null || HDL == null || TG == null) return null;
            if (TG > 400) return null; // Friedewald invalid above 400 mg/dL
            return TC - HDL - TG / 2.2;
        }

        case 'anion_gap': {
            // AG = Na - (Cl + HCO3)
            const Na = get('Na') ?? get('NA');
            const Cl = get('Cl') ?? get('CL');
            const HCO3 = get('HCO3') ?? get('BICARB');
            if (Na == null || Cl == null || HCO3 == null) return null;
            return Na - (Cl + HCO3);
        }

        case 'a_g_ratio': {
            // A:G = ALB / (TP - ALB)
            const ALB = get('ALB');
            const TP = get('TP');
            if (ALB == null || TP == null) return null;
            const globulin = TP - ALB;
            if (globulin <= 0) return null;
            return ALB / globulin;
        }

        case 'egfr_ckd_epi': {
            // CKD-EPI 2021 (creatinine-based, race-free)
            const CREA = get('CREA') ?? get('CREAT');
            const age = patientInfo?.age;
            const gender = patientInfo?.gender?.toUpperCase();
            if (CREA == null || !age || !gender) return null;

            const kappa = gender === 'F' ? 0.7 : 0.9;
            const alpha = gender === 'F' ? -0.241 : -0.302;
            const sexFactor = gender === 'F' ? 1.012 : 1.0;

            const crRatio = CREA / kappa;
            const term = crRatio < 1
                ? Math.pow(crRatio, alpha)
                : Math.pow(crRatio, -1.200);

            const egfr = 142 * term * Math.pow(0.9938, age) * sexFactor;
            return Math.round(egfr * 10) / 10;
        }

        case 'custom':
            // Dangerous — skip
            return null;

        default:
            return null;
    }
}

// GET /api/calculated-tests/compute?orderId=xxx
export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const { searchParams } = new URL(request.url);
        const orderId = searchParams.get('orderId');

        if (!orderId) {
            return NextResponse.json({ error: 'orderId query param is required' }, { status: 400 });
        }

        // Load all active calculated test definitions
        const calcDefs = await db.select().from(calculatedTests).where(eq(calculatedTests.active, true));

        // Load results for this order
        const orderResults = await db.select().from(results).where(eq(results.orderId, orderId));

        // Get the order and patient info
        const orderRows = await db.select().from(orders).where(eq(orders.id, orderId)).limit(1);
        const order = orderRows[0];

        let patientInfo: { age?: number; gender?: string } = {};
        if (order?.patientId) {
            const patientRows = await db.select().from(patients).where(eq(patients.id, order.patientId)).limit(1);
            const patient = patientRows[0];
            if (patient) {
                patientInfo.gender = patient.gender;
                if (patient.dob) {
                    const dob = new Date(patient.dob);
                    const today = new Date();
                    patientInfo.age = Math.floor((today.getTime() - dob.getTime()) / (365.25 * 24 * 60 * 60 * 1000));
                }
            }
        }

        // Build a map of testCode -> numeric value from order results
        const valueMap: Record<string, number> = {};
        for (const r of orderResults) {
            let val: number | null = null;
            try {
                if (r.values) {
                    const parsed = JSON.parse(r.values);
                    if (typeof parsed === 'number') {
                        val = parsed;
                    } else if (typeof parsed?.value === 'number') {
                        val = parsed.value;
                    } else if (typeof parsed?.numeric === 'number') {
                        val = parsed.numeric;
                    }
                }
            } catch { /* ignore parse errors */ }
            if (val != null) {
                valueMap[r.testId] = val;
            }
        }

        // Compute each calculated test
        const computed: Array<{
            testCode: string;
            name: string;
            value: number | null;
            unit: string | null;
            formulaType: string;
            supported: boolean;
        }> = [];

        for (const def of calcDefs) {
            let formula: FormulaDefinition;
            try {
                formula = JSON.parse(def.formula);
            } catch {
                continue;
            }

            const supported = formula.type !== 'custom';
            const value = supported ? computeFormula(formula, valueMap, patientInfo) : null;

            computed.push({
                testCode: def.testCode,
                name: def.name,
                value,
                unit: def.unit,
                formulaType: formula.type,
                supported,
            });
        }

        return NextResponse.json({ orderId, computed });
    } catch (error) {
        console.error('GET /api/calculated-tests/compute error:', error);
        return NextResponse.json({ error: 'Failed to compute derived results' }, { status: 500 });
    }
}
