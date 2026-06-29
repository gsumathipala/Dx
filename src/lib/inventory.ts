
import { db } from '@/db';
import { inventoryItems, inventoryTransactions } from '@/db/schema';
import { eq } from 'drizzle-orm';
import { v4 as uuidv4 } from 'uuid';

export async function consumeReagent(testCode: string, userId: string) {
    // 1. Find reagent associated with test
    // In a real app, we'd have a mapping table (Test -> Reagent).
    // For now, we assume Reagent Name includes the Test Code (e.g., "Glucose Reagent")

    // Naive matching
    const reagents = await db.select().from(inventoryItems);
    const reagent = reagents.find(r => r.name.toLowerCase().includes(testCode.toLowerCase()));

    if (!reagent) {
        console.log(`No reagent found for test ${testCode}`);
        return;
    }

    if (reagent.quantity <= 0) {
        console.warn(`Reagent ${reagent.name} is out of stock!`);
        // We could throw error, or just warn
        return;
    }

    // 2. Decrement
    await db.update(inventoryItems)
        .set({ quantity: reagent.quantity - 1 })
        .where(eq(inventoryItems.id, reagent.id));

    // 3. Log Transaction
    await db.insert(inventoryTransactions).values({
        id: uuidv4(),
        itemId: reagent.id,
        change: -1,
        reason: 'Test Usage',
        userId: userId,
        timestamp: new Date().toISOString()
    });

    console.log(`Consumed 1 unit of ${reagent.name}`);
}
