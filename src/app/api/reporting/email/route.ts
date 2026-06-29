import { NextResponse } from 'next/server';
import { readDb, writeDb, logAudit } from '@/lib/db';
import { cookies } from 'next/headers';

import nodemailer from 'nodemailer';

// Email Provider Logic
async function sendEmailViaProvider(to: string, subject: string, body: string) {
    const db = await readDb();
    const settings = db.settings || {};

    // 1. Simulated Mode (If no SMTP config)
    if (!settings.smtpHost || !settings.smtpUser) {
        console.log(`[SIMULATION] Email to ${to}: ${subject}`);
        await new Promise(r => setTimeout(r, 500));
        return true;
    }

    // 2. Real SMTP Mode
    try {
        const transporter = nodemailer.createTransport({
            host: settings.smtpHost,
            port: Number(settings.smtpPort) || 587,
            secure: Number(settings.smtpPort) === 465, // true for 465, false for other ports
            auth: {
                user: settings.smtpUser,
                pass: settings.smtpPass,
            },
        });

        await transporter.sendMail({
            from: `"${settings.institutionName || 'Dx'}" <${settings.smtpUser}>`,
            to,
            subject,
            text: body, // Plain text for now
            // html: body.replace(/\n/g, '<br>') // Simple HTML conversion if needed
        });

        return true;
    } catch (error) {
        console.error('SMTP Error:', error);
        return false;
    }
}

// GET: Fetch Report Queue
export async function GET() {
    const db = await readDb();
    const queue = db.emailQueue || [];

    // Enrich with patient details for UI
    const enrichedQueue = queue.map((item: any) => {
        const order = db.orders.find((o: any) => o.id === item.orderId);
        const patient = db.patients.find((p: any) => p.id === item.patientId);
        return {
            ...item,
            patientName: patient ? patient.name : 'Unknown',
            accessionNumber: order ? order.accessionNumber : 'Unknown',
            tests: order ? order.tests : [],
            // Default email if not set in queue item
            recipientEmail: item.recipientEmail || (patient ? patient.email : '')
        };
    });

    return NextResponse.json(enrichedQueue);
}

// POST: Add to Queue OR Process Queue
export async function POST(request: Request) {
    const cookieStore = await cookies();
    const session = cookieStore.get('auth_session');
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    const user = JSON.parse(session.value);

    const body = await request.json();
    const { action, orderId, email } = body;

    const db = await readDb();
    if (!db.emailQueue) db.emailQueue = [];

    if (action === 'ADD') {
        // Prevent duplicates
        if (db.emailQueue.some((i: any) => i.orderId === orderId)) {
            return NextResponse.json({ error: 'Order already in queue' }, { status: 400 });
        }

        // Lookup ids
        const order = db.orders.find((o: any) => o.id === orderId);
        if (!order) return NextResponse.json({ error: 'Order not found' }, { status: 404 });

        db.emailQueue.push({
            id: `q-${Date.now()}`,
            orderId: order.id,
            patientId: order.patientId,
            recipientEmail: email, // Optional override
            addedBy: user.username,
            addedAt: new Date().toISOString()
        });
        await writeDb(db);
        return NextResponse.json({ success: true });
    }

    if (action === 'SEND_BATCH') {
        const { items } = body; // Array of queue IDs to send
        const results = [];

        for (const queueId of items) {
            const index = db.emailQueue.findIndex((i: any) => i.id === queueId);
            if (index === -1) continue;

            const item = db.emailQueue[index];
            const recipient = item.recipientEmail || item.patientEmail; // Fallback logic
            const subject = 'Lab Results'; // Define subject for audit log

            if (recipient) {
                // 1. Send Email
                await sendEmailViaProvider(recipient, subject, `Your results for Order ${item.orderId} are attached.`);

                // 2. Audit Trail
                await logAudit(db, 'Email', item.orderId, 'EMAIL_SENT', null, { recipient: recipient, subject: subject }, 'SYSTEM');

                // 3. Remove from Queue
                db.emailQueue.splice(index, 1);
                results.push({ id: queueId, status: 'sent' });
            } else {
                results.push({ id: queueId, status: 'failed', reason: 'No email' });
            }
        }

        await writeDb(db);
        return NextResponse.json({ results });
    }

    // DELETE/REMOVE
    if (action === 'REMOVE') {
        const { id } = body;
        db.emailQueue = db.emailQueue.filter((i: any) => i.id !== id);
        await writeDb(db);
        return NextResponse.json({ success: true });
    }

    return NextResponse.json({ error: 'Invalid action' }, { status: 400 });
}
