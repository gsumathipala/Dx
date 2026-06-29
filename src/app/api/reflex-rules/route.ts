import { NextResponse } from 'next/server';
import { db } from '@/db';
import { reflexRules, testDefinitions } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

async function getCurrentUser() {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return null;
    try {
        return JSON.parse(session.value);
    } catch {
        return null;
    }
}

// GET /api/reflex-rules — returns all reflex rules enriched with test definition names
export async function GET() {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const rules = await db.select().from(reflexRules);

        // Enrich with test definition names
        const enriched = await Promise.all(rules.map(async (rule) => {
            let triggerTestCode = '';
            let triggerTestName = '';
            let addTestName = '';

            try {
                const triggerRows = await db.select().from(testDefinitions).where(
                    eq(testDefinitions.id, rule.triggerTestId)
                ).limit(1);
                if (triggerRows.length > 0) {
                    triggerTestCode = triggerRows[0].code;
                    triggerTestName = triggerRows[0].name;
                }
            } catch { /* non-fatal */ }

            try {
                const addRows = await db.select().from(testDefinitions).where(
                    eq(testDefinitions.id, rule.addTestId)
                ).limit(1);
                if (addRows.length > 0) {
                    addTestName = addRows[0].name;
                }
            } catch { /* non-fatal */ }

            let triggerConditionParsed: Record<string, unknown> = {};
            try {
                triggerConditionParsed = JSON.parse(rule.triggerCondition);
            } catch { /* malformed JSON */ }

            return {
                ...rule,
                triggerTestCode,
                triggerTestName,
                addTestName,
                triggerConditionParsed,
            };
        }));

        return NextResponse.json(enriched);
    } catch (error) {
        console.error('GET reflex-rules error:', error);
        return NextResponse.json({ error: 'Failed to fetch reflex rules' }, { status: 500 });
    }
}

// POST /api/reflex-rules — create a reflex rule (manager/admin only)
// Body: { name, triggerTestId, triggerCondition: { operator, value }, addTestId }
export async function POST(request: Request) {
    const currentUser = await getCurrentUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden: Manager/Admin only' }, { status: 403 });
    }

    try {
        const body = await request.json();
        const { name, triggerTestId, triggerCondition, addTestId } = body;

        if (!name || !triggerTestId || !triggerCondition || !addTestId) {
            return NextResponse.json({
                error: 'Missing required fields: name, triggerTestId, triggerCondition, addTestId'
            }, { status: 400 });
        }

        const validOperators = ['>', '<', '>=', '<=', '=='];
        if (!validOperators.includes(triggerCondition.operator)) {
            return NextResponse.json({
                error: `triggerCondition.operator must be one of: ${validOperators.join(', ')}`
            }, { status: 400 });
        }

        // Look up addTestCode from testDefinitions
        const addTestRows = await db.select().from(testDefinitions).where(eq(testDefinitions.id, addTestId)).limit(1);
        if (addTestRows.length === 0) {
            return NextResponse.json({ error: 'addTestId references a test that does not exist' }, { status: 400 });
        }

        const newRule = {
            id: uuidv4(),
            name,
            triggerTestId,
            triggerCondition: JSON.stringify(triggerCondition),
            addTestId,
            addTestCode: addTestRows[0].code,
            enabled: true,
            createdAt: new Date().toISOString(),
            createdBy: currentUser.username,
        };

        await db.insert(reflexRules).values(newRule);
        return NextResponse.json(newRule, { status: 201 });
    } catch (error) {
        console.error('POST reflex-rule error:', error);
        return NextResponse.json({ error: 'Failed to create reflex rule' }, { status: 500 });
    }
}
