'use client';

import { useState, useEffect, useRef } from 'react';
import { Card } from '@/components/ui/Card';
import { Search, Printer, FileText, CheckCircle, AlertCircle, Clock, Download } from 'lucide-react';
import Link from 'next/link';

interface Patient { id: string; firstName: string; lastName: string; mrn: string; dob: string; gender: string; }
interface Order {
    id: string; patientId: string; accessionNumber: string; status: string;
    timestamp: string; completedAt: string; priority: string; testIds: string[];
}
interface ResultRow { testId: string; testCode: string; testName: string; value: string; units: string; refRange: string; status: string; flags: string; }
interface ReportData { order: Order; patient: Patient; results: ResultRow[]; settings: Record<string, any>; signatures: any[]; }

export default function ReportsPage() {
    const [search, setSearch] = useState('');
    const [orders, setOrders] = useState<Order[]>([]);
    const [patients, setPatients] = useState<Patient[]>([]);
    const [selectedReport, setSelectedReport] = useState<ReportData | null>(null);
    const [loading, setLoading] = useState(false);
    const [settings, setSettings] = useState<any>({});
    const printRef = useRef<HTMLDivElement>(null);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [ordersRes, patientsRes, settingsRes] = await Promise.all([
                fetch('/api/orders'),
                fetch('/api/patients'),
                fetch('/api/admin/settings')
            ]);
            const ordersData = await ordersRes.json();
            setOrders(ordersData.filter((o: Order) => o.status === 'Completed'));
            setPatients(await patientsRes.json());
            if (settingsRes.ok) setSettings(await settingsRes.json());
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchData(); }, []);

    const loadReport = async (order: Order) => {
        setLoading(true);
        try {
            const [resultsRes, signaturesRes] = await Promise.all([
                fetch(`/api/results?orderId=${order.id}`),
                fetch(`/api/signatures?orderId=${order.id}`)
            ]);
            const resultsData = resultsRes.ok ? await resultsRes.json() : [];
            const signaturesData = signaturesRes.ok ? await signaturesRes.json() : [];
            const patient = patients.find(p => p.id === order.patientId);
            if (!patient) return;

            // Flatten composite result into rows (fetch test definitions once)
            const reportResult = resultsData[0];
            const resultValues: Record<string, string> = reportResult?.values?.results || {};
            const testRes = await fetch('/api/admin/tests');
            const tests = testRes.ok ? await testRes.json() : [];
            const resultRows: ResultRow[] = Object.entries(resultValues).map(([testId, value]: [string, any]) => {
                const test = tests.find((t: any) => t.id === testId || t.code === testId);
                return {
                    testId,
                    testCode: test?.code || testId,
                    testName: test?.name || testId,
                    value: String(value),
                    units: test?.units || '',
                    refRange: formatRefRange(test?.referenceRange),
                    status: getValueFlag(String(value), test?.referenceRange),
                    flags: ''
                };
            });
            setSelectedReport({ order, patient, results: resultRows, settings, signatures: signaturesData });
        } finally {
            setLoading(false);
        }
    };

    function formatRefRange(rr: any): string {
        if (!rr) return '-';
        if (typeof rr === 'string') { try { rr = JSON.parse(rr); } catch { return rr; } }
        if (rr.text) return rr.text;
        if (rr.min !== undefined && rr.max !== undefined) return `${rr.min} – ${rr.max}`;
        if (rr.low !== undefined && rr.high !== undefined) return `${rr.low} – ${rr.high}`;
        return '-';
    }

    function getValueFlag(val: string, rr: any): string {
        const num = parseFloat(val);
        if (isNaN(num)) return '';
        if (!rr) return '';
        try { if (typeof rr === 'string') rr = JSON.parse(rr); } catch { return ''; }
        // Canonical shape: { min, max, panicLow, panicHigh }; accept low/high/criticalLow/criticalHigh as aliases
        const critHigh = typeof rr.panicHigh === 'number' ? rr.panicHigh : rr.criticalHigh;
        const critLow = typeof rr.panicLow === 'number' ? rr.panicLow : rr.criticalLow;
        const high = typeof rr.max === 'number' ? rr.max : rr.high;
        const low = typeof rr.min === 'number' ? rr.min : rr.low;
        if (typeof critHigh === 'number' && num > critHigh) return 'C-HIGH';
        if (typeof critLow === 'number' && num < critLow) return 'C-LOW';
        if (typeof high === 'number' && num > high) return 'H';
        if (typeof low === 'number' && num < low) return 'L';
        return '';
    }

    const filtered = orders.filter(o => {
        const patient = patients.find(p => p.id === o.patientId);
        const term = search.toLowerCase();
        return !term ||
            o.accessionNumber?.toLowerCase().includes(term) ||
            patient?.lastName?.toLowerCase().includes(term) ||
            patient?.mrn?.toLowerCase().includes(term);
    });

    const handlePrint = () => {
        const content = printRef.current?.innerHTML;
        if (!content) return;
        const win = window.open('', '', 'width=900,height=1200');
        if (!win) return;
        win.document.write(`<html><head><title>Lab Report</title>
        <style>
            body { font-family: 'Times New Roman', serif; font-size: 12pt; margin: 20mm; color: #000; }
            h1, h2 { margin: 0; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 6px 8px; text-align: left; }
            thead tr { border-bottom: 1.5px solid #000; }
            tbody tr { border-bottom: 1px solid #ddd; }
            .c-high, .c-low { font-weight: bold; color: #cc0000; }
            .high, .low { color: #b45309; }
            .sig-line { margin-top: 30px; border-top: 1px solid #000; padding-top: 6px; font-size: 10pt; }
            @media print { body { margin: 15mm; } }
        </style></head><body>${content}</body></html>`);
        win.document.close();
        win.focus();
        win.print();
        win.close();
    };

    const lab = selectedReport?.settings?.labName || settings?.labName || 'Dx Clinical Laboratory';
    const labAddress = selectedReport?.settings?.labAddress || settings?.labAddress || '';
    const labClia = selectedReport?.settings?.cliaNumber || settings?.cliaNumber || '';

    return (
        <div className="flex h-[calc(100vh-4rem)] gap-6">
            {/* Left Panel */}
            <div className="w-80 flex flex-col gap-4">
                <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-primary-600" />
                    <h1 className="text-xl font-bold text-slate-900">Lab Reports</h1>
                </div>
                <div className="relative">
                    <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                    <input
                        className="input-field pl-9 w-full"
                        placeholder="Search accession, patient, MRN..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>
                <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>{filtered.length} completed reports</span>
                    <Link href="/reports/cumulative" className="text-primary-600 hover:underline font-medium">
                        Cumulative View →
                    </Link>
                </div>
                <div className="flex-1 overflow-y-auto space-y-2 custom-scrollbar">
                    {loading && orders.length === 0 ? (
                        <div className="text-slate-400 text-sm text-center py-8">Loading...</div>
                    ) : filtered.length === 0 ? (
                        <div className="text-slate-400 text-sm text-center py-8">No completed reports found</div>
                    ) : (
                        filtered.map(order => {
                            const patient = patients.find(p => p.id === order.patientId);
                            const isSelected = selectedReport?.order.id === order.id;
                            return (
                                <button
                                    key={order.id}
                                    onClick={() => loadReport(order)}
                                    className={`w-full text-left p-3 rounded-lg border transition-all ${
                                        isSelected
                                            ? 'border-primary-400 bg-primary-50'
                                            : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                                    }`}
                                >
                                    <div className="flex justify-between items-start">
                                        <div className="font-mono text-xs text-primary-700 font-semibold">{order.accessionNumber}</div>
                                        {order.priority === 'STAT' && (
                                            <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-bold">STAT</span>
                                        )}
                                    </div>
                                    <div className="font-medium text-slate-800 text-sm mt-0.5">
                                        {patient ? `${patient.lastName}, ${patient.firstName}` : order.patientId}
                                    </div>
                                    <div className="text-xs text-slate-500 mt-1">
                                        {patient?.mrn} · {order.completedAt ? new Date(order.completedAt).toLocaleDateString() : new Date(order.timestamp).toLocaleDateString()}
                                    </div>
                                </button>
                            );
                        })
                    )}
                </div>
            </div>

            {/* Right Panel — Report Preview */}
            <div className="flex-1 overflow-y-auto">
                {selectedReport ? (
                    <div className="space-y-4">
                        {/* Toolbar */}
                        <div className="flex items-center gap-3 p-4 bg-white border border-slate-200 rounded-lg">
                            <span className="font-semibold text-slate-700">
                                {selectedReport.patient.lastName}, {selectedReport.patient.firstName}
                            </span>
                            <span className="text-slate-400">·</span>
                            <span className="font-mono text-primary-700 text-sm">{selectedReport.order.accessionNumber}</span>
                            <div className="flex-1" />
                            <button
                                onClick={handlePrint}
                                className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium"
                            >
                                <Printer className="w-4 h-4" />
                                Print / PDF
                            </button>
                        </div>

                        {/* Report Body */}
                        <div className="bg-white border border-slate-200 rounded-lg shadow-sm p-10 font-serif" ref={printRef}>
                            {/* Lab Header */}
                            <div className="border-b-2 border-slate-800 pb-4 mb-6 flex justify-between items-start">
                                <div>
                                    <h1 className="text-xl font-bold tracking-tight">{lab}</h1>
                                    {labAddress && <div className="text-sm text-slate-600">{labAddress}</div>}
                                    {labClia && <div className="text-sm text-slate-600">CLIA # {labClia}</div>}
                                </div>
                                <div className="text-right">
                                    <div className="text-lg font-bold text-slate-800">FINAL REPORT</div>
                                    <div className="text-sm text-slate-500 mt-1">
                                        Printed: {new Date().toLocaleString()}
                                    </div>
                                    {selectedReport.order.priority === 'STAT' && (
                                        <div className="mt-1 text-red-700 font-bold text-sm border border-red-300 px-2 py-0.5 rounded inline-block">
                                            STAT
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Patient Info */}
                            <div className="grid grid-cols-2 gap-8 mb-6 text-sm">
                                <div className="space-y-1">
                                    <div><span className="font-semibold">Patient:</span> {selectedReport.patient.lastName}, {selectedReport.patient.firstName}</div>
                                    <div><span className="font-semibold">MRN:</span> {selectedReport.patient.mrn}</div>
                                    <div><span className="font-semibold">Date of Birth:</span> {selectedReport.patient.dob}</div>
                                    <div><span className="font-semibold">Gender:</span> {selectedReport.patient.gender}</div>
                                </div>
                                <div className="space-y-1">
                                    <div><span className="font-semibold">Accession #:</span> <span className="font-mono">{selectedReport.order.accessionNumber}</span></div>
                                    <div><span className="font-semibold">Ordered:</span> {new Date(selectedReport.order.timestamp).toLocaleString()}</div>
                                    <div><span className="font-semibold">Completed:</span> {selectedReport.order.completedAt ? new Date(selectedReport.order.completedAt).toLocaleString() : '-'}</div>
                                    <div><span className="font-semibold">Report Date:</span> {new Date().toLocaleDateString()}</div>
                                </div>
                            </div>

                            {/* Results Table */}
                            <table className="w-full text-sm mb-6">
                                <thead>
                                    <tr className="border-b border-slate-800">
                                        <th className="py-2 text-left font-semibold">Test</th>
                                        <th className="py-2 text-left font-semibold">Result</th>
                                        <th className="py-2 text-left font-semibold">Flag</th>
                                        <th className="py-2 text-left font-semibold">Reference Range</th>
                                        <th className="py-2 text-left font-semibold">Units</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {selectedReport.results.length === 0 ? (
                                        <tr>
                                            <td colSpan={5} className="py-4 text-center text-slate-400 italic">No result values available</td>
                                        </tr>
                                    ) : (
                                        selectedReport.results.map((row, i) => (
                                            <tr key={i} className="border-b border-slate-100">
                                                <td className="py-2 text-slate-700">{row.testName}</td>
                                                <td className={`py-2 font-medium ${row.status.startsWith('C-') ? 'text-red-700' : row.status ? 'text-amber-700' : 'text-slate-900'}`}>
                                                    {row.value}
                                                </td>
                                                <td className="py-2">
                                                    {row.status && (
                                                        <span className={getFlagStyle(row.status)}>{row.status}</span>
                                                    )}
                                                </td>
                                                <td className="py-2 text-slate-500 text-xs">{row.refRange}</td>
                                                <td className="py-2 text-slate-500 text-xs">{row.units}</td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>

                            {/* Signatures */}
                            <div className="border-t border-slate-300 pt-4 mt-6">
                                {selectedReport.signatures.length > 0 ? (
                                    <div className="grid grid-cols-2 gap-8 text-sm">
                                        {selectedReport.signatures.map((sig: any, i: number) => (
                                            <div key={i} className="border-t border-slate-400 pt-2">
                                                <div className="font-semibold">{sig.signatureType === 'clinical' ? 'Clinically Verified By' : 'Technically Validated By'}</div>
                                                <div className="mt-1">{sig.signedBy}</div>
                                                <div className="text-slate-500 text-xs">{sig.signedAt ? new Date(sig.signedAt).toLocaleString() : ''}</div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-sm text-slate-500 italic">
                                        Electronically authorized. Signed by laboratory information system.
                                    </div>
                                )}
                            </div>

                            {/* Footer */}
                            <div className="mt-8 pt-4 border-t border-slate-200 text-xs text-slate-400 text-center">
                                This report is confidential and intended solely for the requesting clinician. · Dx LIS
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center text-slate-400">
                        <FileText className="w-16 h-16 mb-4 opacity-30" />
                        <p className="text-lg font-medium">Select a completed order to view the report</p>
                        <p className="text-sm mt-1">Reports include all verified results and electronic signatures</p>
                    </div>
                )}
            </div>
        </div>
    );

    function getFlagStyle(flag: string) {
        if (flag.startsWith('C-')) return 'font-bold text-red-700';
        if (flag === 'H' || flag === 'L') return 'text-amber-700 font-medium';
        return '';
    }
}
