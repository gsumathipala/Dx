import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const type = searchParams.get('type');
    const db = await readDb();

    if (type === 'recipes') return NextResponse.json(db.recipes || []);
    if (type === 'runs') return NextResponse.json(db.productionRuns || []);

    return NextResponse.json({ error: 'Invalid type' }, { status: 400 });
}

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const { type, data } = body;
        const db = await readDb();

        if (type === 'recipe') {
            if (!db.recipes) db.recipes = [];
            const newRecipe = { id: Date.now().toString(), ...data };
            db.recipes.push(newRecipe);
            await writeDb(db);
            return NextResponse.json(newRecipe);
        } else if (type === 'run') {
            if (!db.productionRuns) db.productionRuns = [];

            // 1. Create Production Run
            const newRun = {
                id: Date.now().toString(),
                timestamp: new Date().toISOString(),
                ...data
            };
            db.productionRuns.push(newRun);

            // 2. Add to Inventory automatically
            if (!db.inventory) db.inventory = [];
            const recipe = db.recipes.find((r: any) => r.id === data.recipeId);
            if (recipe) {
                db.inventory.push({
                    id: `prod-${newRun.id}`,
                    name: recipe.name, // e.g. "Chocolate Agar"
                    lotNumber: newRun.lotNumber,
                    quantity: newRun.quantity,
                    unit: 'plates', // Simple assumption
                    expiryDate: newRun.expiryDate,
                    lowStockThreshold: 10
                });
            }

            await writeDb(db);
            return NextResponse.json(newRun);
        }

        return NextResponse.json({ error: 'Invalid type' }, { status: 400 });
    } catch (error) {
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}
