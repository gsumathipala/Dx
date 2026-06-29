import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { cookies } from 'next/headers';
import { writeFile } from 'fs/promises';
import { join } from 'path';
import { getAuthUser } from '@/lib/auth';

export async function GET() {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const db = await readDb();
    return NextResponse.json(db.documents || []);
}

export async function POST(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const currentUser = JSON.parse(session.value);
    if (!['admin', 'manager'].includes(currentUser.role)) {
        return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    try {
        const formData = await request.formData();

        const file = formData.get('file') as File | null;
        const title = formData.get('title') as string;
        const category = formData.get('category') as string;
        const version = formData.get('version') as string || '1.0';
        const effectiveDate = formData.get('effectiveDate') as string;
        const action = formData.get('action') as string; // 'CREATE' or 'REVISE'

        let filePath = '';

        // Handle File Upload
        if (file) {
            const bytes = await file.arrayBuffer();
            const buffer = Buffer.from(bytes);
            const filename = `${Date.now()}-${file.name.replace(/[^a-zA-Z0-9.-]/g, '_')}`;
            const uploadDir = join(process.cwd(), 'public', 'uploads', 'documents');

            await writeFile(join(uploadDir, filename), buffer);
            filePath = `/uploads/documents/${filename}`;
        } else if (action === 'UPDATE_META') {
            // Keep existing path if just updating meta
            // Logic handled below
        }

        const db = await readDb();
        if (!db.documents) db.documents = [];

        if (action === 'REVISE') {
            const parentId = formData.get('parentId') as string;
            // 1. Mark old doc as Obsolete
            const oldDocIndex = db.documents.findIndex((d: any) => d.id === parentId);
            if (oldDocIndex !== -1) {
                db.documents[oldDocIndex].status = 'Obsolete';
                db.documents[oldDocIndex].obsoleteDate = new Date().toISOString();
            }
        }

        const newDoc = {
            id: `doc-${Date.now()}`,
            title,
            category,
            version,
            status: 'Active',
            filePath, // If updating meta without file, this might be issue. But for Revision file is required usually.
            effectiveDate: effectiveDate || new Date().toISOString(),
            uploadedBy: currentUser.username,
            uploadedAt: new Date().toISOString()
        };

        db.documents.push(newDoc);
        await logAudit(db, 'Document', newDoc.id, action || 'CREATE', null, newDoc.id, currentUser.username);

        await writeDb(db);
        return NextResponse.json({ success: true, doc: newDoc });

    } catch (e: any) {
        console.error('Upload Error:', e);
        return NextResponse.json({ error: e.message || 'Upload failed' }, { status: 500 });
    }
}

export async function PUT(request: Request) {
    // For Status Updates (e.g. Obsolete)
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const currentUser = JSON.parse(session.value);
    if (!['admin', 'manager'].includes(currentUser.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

    try {
        const { id, status } = await request.json();
        const db = await readDb();
        const doc = db.documents.find((d: any) => d.id === id);
        if (doc) {
            doc.status = status;
            await writeDb(db);
            return NextResponse.json({ success: true });
        }
        return NextResponse.json({ error: 'Not found' }, { status: 404 });
    } catch (e) { return NextResponse.json({ error: 'Error' }, { status: 500 }); }
}
