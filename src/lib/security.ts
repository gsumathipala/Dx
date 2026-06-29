
import crypto from 'crypto';
import { Readable, Transform } from 'stream';

const ALGORITHM = 'aes-256-gcm';

/**
 * Derives a 32-byte key from a password using scrypt (secure implementation)
 */
export async function deriveKey(password: string, salt: Buffer): Promise<Buffer> {
    return new Promise((resolve, reject) => {
        crypto.scrypt(password, salt, 32, (err, derivedKey) => {
            if (err) reject(err);
            else resolve(derivedKey as Buffer);
        });
    });
}

/**
 * Creates a transform stream that encrypts data with AES-256-GCM
 * Output format: [salt: 16][iv: 16][authTag: 16][encryptedData...]
 * Note: authTag is usually at the end, but GCM streams need to calculate it.
 * Simplified for file-based: We will just use standard crypto primitives.
 * 
 * Better approach for single file: 
 * 1. Generate Salt & IV.
 * 2. Create Cipher.
 * 3. Prepended Salt & IV to output.
 * 4. Pipe data.
 * 5. Append AuthTag at END.
 */
export async function createEncryptionDetails(password: string) {
    const salt = crypto.randomBytes(16);
    const iv = crypto.randomBytes(16);
    const key = await deriveKey(password, salt);
    const cipher = crypto.createCipheriv(ALGORITHM, key, iv);

    return { cipher, salt, iv };
}

export async function createDecryptionDetails(password: string, salt: Buffer, iv: Buffer) {
    const key = await deriveKey(password, salt);
    const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
    return decipher;
}
