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
        const file = formData.get('file') as File;
        const password = formData.get('password') as string;

        if (!file || !password) {
            return NextResponse.json({ error: 'File and password required' }, { status: 400 });
        }

        const buffer = Buffer.from(await file.arrayBuffer());

        // Format: [salt:32][iv:16][authTag:16][encryptedData]
        if (buffer.length < 64) {
            return NextResponse.json({ error: 'Invalid backup file (too small)' }, { status: 400 });
        }

        const salt = buffer.subarray(0, 32);
        const iv = buffer.subarray(32, 48);
        const authTag = buffer.subarray(48, 64);
        const encryptedData = buffer.subarray(64);

        const key = await new Promise<Buffer>((resolve, reject) =>
            crypto.scrypt(password, salt, 32, (err, k) => err ? reject(err) : resolve(k as Buffer))
        );

        const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
        decipher.setAuthTag(authTag);

        let decrypted: Buffer;
        try {
            decrypted = Buffer.concat([decipher.update(encryptedData), decipher.final()]);
        } catch {
            return NextResponse.json({ error: 'Decryption failed — wrong password or corrupted file' }, { status: 400 });
        }

        // Atomic write: temp file then rename
        const tempPath = DB_FILE + '.restore_tmp';
        fs.writeFileSync(tempPath, decrypted);
        fs.renameSync(tempPath, DB_FILE);

        return NextResponse.json({ success: true, message: 'Database restored successfully. Please restart the application.' });

    } catch (error) {
        console.error('Restore error:', error);
        return NextResponse.json({ error: 'Restore failed' }, { status: 500 });
    }
}
