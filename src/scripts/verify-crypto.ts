
import fs from 'fs';
import path from 'path';
import { createEncryptionDetails, createDecryptionDetails } from '../lib/security';

async function testCrypto() {
    console.log('--- Starting Crypto Verification ---');
    const password = 'secure-password-123';
    const originalText = 'This is a secret database content.';

    // 1. Encrypt
    console.log('1. Encrypting...');
    const { cipher, salt, iv } = await createEncryptionDetails(password);

    let encrypted = cipher.update(originalText, 'utf8');
    encrypted = Buffer.concat([encrypted, cipher.final()]);
    const tag = cipher.getAuthTag();

    console.log('   Encrypted Buffer Size:', encrypted.length);
    console.log('   Tag:', tag.toString('hex'));

    // 2. Decrypt (Success Case)
    console.log('2. Decrypting (Correct Password)...');
    const decipher = await createDecryptionDetails(password, salt, iv);
    decipher.setAuthTag(tag);

    let decrypted = decipher.update(encrypted);
    decrypted = Buffer.concat([decrypted, decipher.final()]);

    console.log('   Decrypted:', decrypted.toString('utf8'));

    if (decrypted.toString('utf8') === originalText) {
        console.log('   ✅ Success: Text matches.');
    } else {
        console.error('   ❌ Failed: Text mismatch.');
    }

    // 3. Decrypt (Failure Case - Wrong Password)
    console.log('3. Decrypting (Wrong Password)...');
    try {
        const wrongDecipher = await createDecryptionDetails('wrong-pass', salt, iv);
        wrongDecipher.setAuthTag(tag); // Tag matches data, but key is wrong

        let wrongDecrypted = wrongDecipher.update(encrypted);
        wrongDecrypted = Buffer.concat([wrongDecrypted, wrongDecipher.final()]);
        console.error('   ❌ Failed: Should have thrown error.');
    } catch (e: any) {
        console.log('   ✅ Success: Decryption failed as expected:', e.message);
    }

    // 4. Decrypt (Failure Case - Tampered Data)
    console.log('4. Decrypting (Tampered Data)...');
    try {
        const tampered = Buffer.from(encrypted);
        tampered[0] = tampered[0] ^ 1; // Flip a bit

        const tamperDecipher = await createDecryptionDetails(password, salt, iv);
        tamperDecipher.setAuthTag(tag);

        let tDecrypted = tamperDecipher.update(tampered);
        tDecrypted = Buffer.concat([tDecrypted, tamperDecipher.final()]);
        console.error('   ❌ Failed: Should have thrown error (Auth Tag Mismatch).');
    } catch (e: any) {
        console.log('   ✅ Success: Decryption failed as expected:', e.message);
    }
}

testCrypto().catch(console.error);
