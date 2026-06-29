import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

const ALGORITHM = 'aes-256-gcm';
const DB_FILE = path.join(process.cwd(), 'sqlite_v2.db');

export async function POST(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const user = JSON.parse(session.value);
    if (user.role !== 'admin') return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

    try {
        const formData = await request.formData();
        const password = formData.get('password') as string;

        if (!password) return NextResponse.json({ error: 'Password required' }, { status: 400 });
        if (!fs.existsSync(DB_FILE)) return NextResponse.json({ error: 'Database file not found' }, { status: 404 });

        // Derive key with scrypt (more secure than pbkdf2 for this use case)
        const salt = crypto.randomBytes(32);
        const iv = crypto.randomBytes(16);
        const key = await new Promise<Buffer>((resolve, reject) =>
            crypto.scrypt(password, salt, 32, (err, k) => err ? reject(err) : resolve(k as Buffer))
        );

        const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
        const fileData = fs.readFileSync(DB_FILE);
        const encrypted = Buffer.concat([cipher.update(fileData), cipher.final()]);
        const authTag = cipher.getAuthTag();

        // Format: [salt:32][iv:16][authTag:16][encryptedData]
        const output = Buffer.concat([salt, iv, authTag, encrypted]);

        const filename = `dx_backup_${new Date().toISOString().slice(0, 10)}.enc`;

        return new NextResponse(output, {
            headers: {
                'Content-Type': 'application/octet-stream',
                'Content-Disposition': `attachment; filename="${filename}"`
            }
        });

    } catch (error) {
        console.error('Backup error:', error);
        return NextResponse.json({ error: 'Backup failed' }, { status: 500 });
    }
}
