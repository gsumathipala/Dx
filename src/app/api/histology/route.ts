import { NextResponse } from 'next/server';
import { readDb, writeDb } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const { searchParams } = new URL(request.url);
    const accessionNumber = searchParams.get('accessionNumber');
    const db = await readDb();

    let blocks = db.histoBlocks || [];
    let slides = db.histoSlides || [];

    if (accessionNumber) {
        blocks = blocks.filter((b: any) => b.accessionNumber === accessionNumber);
        const blockIds = blocks.map((b: any) => b.id);
        slides = slides.filter((s: any) => blockIds.includes(s.blockId));
    }

    return NextResponse.json({ blocks, slides });
}

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const { action, accessionNumber, blockId, label, notes, count } = body;
        const db = await readDb();

        // Ensure collections
        if (!db.histoBlocks) db.histoBlocks = [];
        if (!db.histoSlides) db.histoSlides = [];

        if (action === 'grossing') {
            // Create BLOCKS
            // Input: accessionNumber, count (how many blocks), notes
            const newBlocks = [];
            const timestamp = new Date().toISOString();

            // Generate IDs like "ACC-123-A", "ACC-123-B"
            const startChar = 65; // A
            const existingCount = db.histoBlocks.filter((b: any) => b.accessionNumber === accessionNumber).length;

            for (let i = 0; i < count; i++) {
                const suffix = String.fromCharCode(startChar + existingCount + i);
                const fullId = `${accessionNumber}-${suffix}`;
                const block = {
                    id: fullId,
                    accessionNumber,
                    label: fullId,
                    type: 'Block',
                    status: 'Processing',
                    notes: notes || '',
                    timestamp
                };
                db.histoBlocks.push(block);
                newBlocks.push(block);
            }
            await writeDb(db);
            return NextResponse.json({ message: `${count} Blocks Created`, blocks: newBlocks });
        }

        else if (action === 'microtomy') {
            // Create SLIDES
            // Input: blockId (e.g. ACC-123-A), count, notes
            const newSlides = [];
            const timestamp = new Date().toISOString();
            const existingCount = db.histoSlides.filter((s: any) => s.blockId === blockId).length;

            for (let i = 0; i < count; i++) {
                const suffix = existingCount + i + 1;
                const fullId = `${blockId}-${suffix}`;
                const slide = {
                    id: fullId,
                    blockId,
                    accessionNumber, // Denormalized for easier search
                    label: fullId,
                    type: 'Slide',
                    status: 'Unstained',
                    notes: notes || '',
                    timestamp
                };
                db.histoSlides.push(slide);
                newSlides.push(slide);
            }
            await writeDb(db);
            return NextResponse.json({ message: `${count} Slides Created`, slides: newSlides });
        }

        return NextResponse.json({ error: 'Invalid Action' }, { status: 400 });

    } catch (error) {
        return NextResponse.json({ error: 'Failed' }, { status: 500 });
    }
}
