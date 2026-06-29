import { NextResponse } from 'next/server';
import { generateZPLLabel } from '@/lib/db';
import { getAuthUser } from '@/lib/auth';

function escapeHtml(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/**
 * Label Generation API
 * 
 * Generates ZPL (Zebra Programming Language) barcode labels
 * Compatible with most thermal label printers
 */

export async function POST(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    try {
        const body = await request.json();
        const { patientName, accessionNumber, collectionDate, specimenType, format } = body;

        if (!patientName || !accessionNumber) {
            return NextResponse.json({
                error: 'Missing required fields: patientName, accessionNumber'
            }, { status: 400 });
        }

        const formattedDate = collectionDate
            ? new Date(collectionDate).toLocaleDateString()
            : new Date().toLocaleDateString();

        if (format === 'html') {
            // Return HTML for browser printing — all user values are HTML-escaped to prevent XSS
            const safeName = escapeHtml(patientName);
            const safeAccession = escapeHtml(accessionNumber);
            const safeDate = escapeHtml(formattedDate);
            const safeType = escapeHtml(specimenType || 'General');
            const html = `
<!DOCTYPE html>
<html>
<head>
    <style>
        @page { size: 2in 1in; margin: 0; }
        body {
            font-family: Arial, sans-serif;
            padding: 5mm;
            width: 2in;
        }
        .label {
            border: 1px solid #000;
            padding: 3mm;
        }
        .patient-name {
            font-size: 10pt;
            font-weight: bold;
            margin-bottom: 2mm;
        }
        .barcode {
            font-family: 'Libre Barcode 128', cursive;
            font-size: 32pt;
            text-align: center;
            margin: 2mm 0;
        }
        .accession {
            font-size: 8pt;
            text-align: center;
            margin-bottom: 2mm;
        }
        .meta {
            font-size: 7pt;
            color: #333;
        }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Libre+Barcode+128&display=swap" rel="stylesheet">
</head>
<body>
    <div class="label">
        <div class="patient-name">${safeName}</div>
        <div class="barcode">${safeAccession}</div>
        <div class="accession">${safeAccession}</div>
        <div class="meta">
            Collected: ${safeDate}<br/>
            Type: ${safeType}
        </div>
    </div>
    <script>window.print();</script>
</body>
</html>`;
            return new NextResponse(html, {
                headers: { 'Content-Type': 'text/html' }
            });
        }

        // Default: ZPL format
        const zpl = generateZPLLabel(
            accessionNumber,
            patientName,
            formattedDate
        );

        return new NextResponse(zpl, {
            headers: {
                'Content-Type': 'text/plain',
                'Content-Disposition': `attachment; filename="label-${accessionNumber}.zpl"`
            }
        });

    } catch (error) {
        console.error('Label generation error:', error);
        return NextResponse.json({ error: 'Failed to generate label' }, { status: 500 });
    }
}

// GET: Generate label from query params
export async function GET(request: Request) {
    const currentUser = await getAuthUser();
    if (!currentUser) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    const { searchParams } = new URL(request.url);

    const patientName = searchParams.get('patientName');
    const accessionNumber = searchParams.get('accession');
    const collectionDate = searchParams.get('date');
    const specimenType = searchParams.get('type');
    const format = searchParams.get('format') || 'zpl';

    if (!patientName || !accessionNumber) {
        return NextResponse.json({
            error: 'Missing required params: patientName, accession'
        }, { status: 400 });
    }

    const formattedDate = collectionDate
        ? new Date(collectionDate).toLocaleDateString()
        : new Date().toLocaleDateString();

    if (format === 'html') {
        const safeName = escapeHtml(patientName);
        const safeAccession = escapeHtml(accessionNumber);
        const safeDate = escapeHtml(formattedDate);
        const safeType = escapeHtml(specimenType || 'General');
        const html = `
<!DOCTYPE html>
<html>
<head>
    <style>
        @page { size: 2in 1in; margin: 0; }
        body { font-family: Arial, sans-serif; padding: 5mm; }
        .patient-name { font-size: 10pt; font-weight: bold; }
        .barcode { font-family: 'Libre Barcode 128', cursive; font-size: 32pt; }
        .accession { font-size: 8pt; }
        .meta { font-size: 7pt; color: #333; }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Libre+Barcode+128&display=swap" rel="stylesheet">
</head>
<body>
    <div class="patient-name">${safeName}</div>
    <div class="barcode">${safeAccession}</div>
    <div class="accession">${safeAccession}</div>
    <div class="meta">Collected: ${safeDate} | Type: ${safeType}</div>
</body>
</html>`;
        return new NextResponse(html, { headers: { 'Content-Type': 'text/html' } });
    }

    const zpl = generateZPLLabel(
        accessionNumber,
        patientName,
        formattedDate
    );

    return new NextResponse(zpl, {
        headers: { 'Content-Type': 'text/plain' }
    });
}
