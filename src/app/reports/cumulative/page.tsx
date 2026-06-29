'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card } from '@/components/ui/Card';
import { Search, Printer, X } from 'lucide-react';

interface Patient {
    id: string;
    firstName: string;
    lastName: string;
    mrn: string;
    dob: string;
    gender: string;
}

interface TestMeta {
    testId: string;
    testCode: string;
    testName: string;
    units: string;
    referenceRange: Record<string, unknown> | string | null;
}

interface VisitResult {
    value: string;
    status: string;
    flags: string[];
}

interface Visit {
    orderId: string;
    accessionNumber: string;
    date: string;
    results: Record<string, VisitResult>;
}

interface CumulativeData {
    patient: { name: string; mrn: string; dob: string; gender: string };
    tests: TestMeta[];
    visits: Visit[];
}

function formatRefRange(rr: Record<string, unknown> | string | null): string {
    if (!rr) return '';
    if (typeof rr === 'string') return rr;
    if (typeof rr === 'object') {
        const low = rr.low ?? rr.min;
        const high = rr.high ?? rr.max;
        if (low !== undefined && high !== undefined) return `${low} – ${high}`;
        if (rr.text) return String(rr.text);
    }
    return '';
}

function getCellClass(flags: string[]): string {
    if (flags.includes('CH') || flags.includes('CritHigh')) return 'bg-red-100 text-red-800 font-bold';
    if (flags.includes('CL') || flags.includes('CritLow')) return 'bg-red-100 text-red-800 font-bold';
    if (flags.includes('C')) return 'bg-red-100 text-red-800 font-bold';
    if (flags.includes('H')) return 'bg-orange-100 text-orange-700 font-semibold';
    if (flags.includes('L')) return 'bg-blue-100 text-blue-700 font-semibold';
    return 'text-slate-800';
}

export default function CumulativeReportPage() {
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState<Patient[]>([]);
    const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
    const [data, setData] = useState<CumulativeData | null>(null);
    const [selectedTestCodes, setSelectedTestCodes] = useState<Set<string>>(new Set());
    const [loading, setLoading] = useState(false);
    const [searching, setSearching] = useState(false);
    const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        if (!searchQuery.trim()) {
            setSearchResults([]);
            return;
        }
        if (searchTimeout.current) clearTimeout(searchTimeout.current);
        searchTimeout.current = setTimeout(async () => {
            setSearching(true);
            try {
                const res = await fetch(`/api/patients?search=${encodeURIComponent(searchQuery)}`);
                const json = await res.json();
                setSearchResults(Array.isArray(json) ? json : (json.patients ?? []));
            } finally {
                setSearching(false);
            }
        }, 300);
    }, [searchQuery]);

    const selectPatient = async (patient: Patient) => {
        setSelectedPatient(patient);
        setSearchQuery('');
        setSearchResults([]);
        setSelectedTestCodes(new Set());
        setLoading(true);
        try {
            const res = await fetch(`/api/reports/cumulative?patientId=${patient.id}`);
            const json = await res.json();
            setData(json);
        } finally {
            setLoading(false);
        }
    };

    const toggleTestCode = (code: string) => {
        setSelectedTestCodes((prev) => {
            const next = new Set(prev);
            if (next.has(code)) next.delete(code);
            else next.add(code);
            return next;
        });
    };

    const displayedTests = data
        ? selectedTestCodes.size === 0
            ? data.tests
            : data.tests.filter((t) => selectedTestCodes.has(t.testCode))
        : [];

    const handlePrint = () => window.print();

    return (
        <div className="min-h-screen bg-slate-50 p-6">
            <div className="max-w-full mx-auto space-y-4">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">Cumulative Result Flowsheet</h1>
                        <p className="text-slate-500 text-sm mt-1">View historical results across all visits for a patient</p>
                    </div>
                    {data && (
                        <button
                            onClick={handlePrint}
                            className="flex items-center gap-2 px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-800 text-sm print:hidden"
                        >
                            <Printer size={16} />
                            Print
                        </button>
                    )}
                </div>

                {/* Patient Search */}
                <Card title="Patient Search" className="print:hidden">
                    <div className="relative">
                        <div className="flex items-center gap-2 border border-slate-300 rounded-lg px-3 py-2 bg-white focus-within:ring-2 focus-within:ring-blue-500">
                            <Search size={16} className="text-slate-400" />
                            <input
                                type="text"
                                placeholder="Search by name or MRN..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="flex-1 outline-none text-sm text-slate-800 placeholder-slate-400"
                            />
                            {searching && <span className="text-xs text-slate-400">Searching...</span>}
                        </div>
                        {searchResults.length > 0 && (
                            <div className="absolute z-10 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
                                {searchResults.map((p) => (
                                    <button
                                        key={p.id}
                                        onClick={() => selectPatient(p)}
                                        className="w-full text-left px-4 py-3 hover:bg-slate-50 border-b border-slate-100 last:border-0"
                                    >
                                        <span className="font-medium text-slate-900">
                                            {p.firstName} {p.lastName}
                                        </span>
                                        <span className="ml-2 text-xs text-slate-500">MRN: {p.mrn}</span>
                                        <span className="ml-2 text-xs text-slate-400">{p.gender} · DOB: {p.dob}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </Card>

                {/* Patient Header */}
                {selectedPatient && data && (
                    <>
                        <Card className="bg-blue-50 border-blue-200">
                            <div className="flex items-start justify-between">
                                <div>
                                    <p className="text-xs text-blue-500 font-semibold uppercase tracking-wide">Selected Patient</p>
                                    <h2 className="text-xl font-bold text-slate-900 mt-1">{data.patient.name}</h2>
                                    <div className="flex gap-4 mt-2 text-sm text-slate-600">
                                        <span>MRN: <strong>{data.patient.mrn}</strong></span>
                                        <span>DOB: <strong>{data.patient.dob}</strong></span>
                                        <span>Gender: <strong>{data.patient.gender}</strong></span>
                                    </div>
                                </div>
                                <button
                                    onClick={() => { setSelectedPatient(null); setData(null); }}
                                    className="text-slate-400 hover:text-slate-700 print:hidden"
                                >
                                    <X size={18} />
                                </button>
                            </div>
                        </Card>

                        {/* Test Filter Chips */}
                        {data.tests.length > 0 && (
                            <div className="flex flex-wrap gap-2 print:hidden">
                                <span className="text-xs text-slate-500 self-center">Filter tests:</span>
                                {data.tests.map((t) => (
                                    <button
                                        key={t.testCode}
                                        onClick={() => toggleTestCode(t.testCode)}
                                        className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                                            selectedTestCodes.has(t.testCode)
                                                ? 'bg-blue-600 text-white border-blue-600'
                                                : 'bg-white text-slate-700 border-slate-300 hover:border-blue-400'
                                        }`}
                                    >
                                        {t.testCode}
                                    </button>
                                ))}
                                {selectedTestCodes.size > 0 && (
                                    <button
                                        onClick={() => setSelectedTestCodes(new Set())}
                                        className="px-3 py-1 rounded-full text-xs font-medium text-slate-500 hover:text-slate-700"
                                    >
                                        Clear filter
                                    </button>
                                )}
                            </div>
                        )}

                        {/* Results Flowsheet Table */}
                        {loading ? (
                            <Card title="Loading...">
                                <div className="text-slate-400 text-sm py-8 text-center">Fetching cumulative results...</div>
                            </Card>
                        ) : displayedTests.length === 0 ? (
                            <Card title="No Results">
                                <div className="text-slate-400 text-sm py-8 text-center">No completed results found for this patient.</div>
                            </Card>
                        ) : (
                            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
                                <table className="min-w-full text-sm border-collapse">
                                    <thead>
                                        <tr className="bg-slate-50">
                                            <th className="sticky left-0 bg-slate-50 z-10 px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wide border-b border-r border-slate-200 min-w-[200px]">
                                                Test / Reference
                                            </th>
                                            {data.visits.map((v) => (
                                                <th
                                                    key={v.orderId}
                                                    className="px-4 py-3 text-center text-xs font-semibold text-slate-600 border-b border-r border-slate-200 min-w-[120px]"
                                                >
                                                    <div className="font-mono text-slate-800">{v.accessionNumber}</div>
                                                    <div className="text-slate-400 font-normal mt-0.5">
                                                        {new Date(v.date).toLocaleDateString()}
                                                    </div>
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {displayedTests.map((test, idx) => (
                                            <tr key={test.testId} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                                                <td className="sticky left-0 z-10 px-4 py-3 border-b border-r border-slate-200 bg-inherit">
                                                    <div className="font-medium text-slate-900">{test.testName}</div>
                                                    <div className="text-xs text-slate-400 mt-0.5">
                                                        {test.testCode}{test.units ? ` · ${test.units}` : ''}
                                                    </div>
                                                    {test.referenceRange && (
                                                        <div className="text-xs text-slate-400 mt-0.5">
                                                            Ref: {formatRefRange(test.referenceRange as Record<string, unknown>)}
                                                        </div>
                                                    )}
                                                </td>
                                                {data.visits.map((v) => {
                                                    const cell = v.results[test.testCode];
                                                    return (
                                                        <td
                                                            key={v.orderId}
                                                            className={`px-4 py-3 text-center border-b border-r border-slate-200 ${cell ? getCellClass(cell.flags) : 'text-slate-300'}`}
                                                        >
                                                            {cell ? (
                                                                <>
                                                                    <span>{cell.value}</span>
                                                                    {cell.flags.length > 0 && (
                                                                        <span className="ml-1 text-xs opacity-75">
                                                                            {cell.flags.join(',')}
                                                                        </span>
                                                                    )}
                                                                </>
                                                            ) : (
                                                                <span className="text-slate-200">—</span>
                                                            )}
                                                        </td>
                                                    );
                                                })}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </>
                )}

                {!selectedPatient && !loading && (
                    <Card title="">
                        <div className="text-center py-12 text-slate-400">
                            <Search size={40} className="mx-auto mb-3 opacity-30" />
                            <p className="text-sm">Search for a patient above to view their cumulative result flowsheet.</p>
                        </div>
                    </Card>
                )}
            </div>
        </div>
    );
}
