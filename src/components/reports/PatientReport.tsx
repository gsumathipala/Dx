import React from 'react';
import { formatDateTime } from '@/lib/utils';

// Styles for printing
import '@/app/globals.css';

interface PatientReportProps {
    order: any;
    results: any; // { results: map, attachments: map, lotNumbers: map }
    tests: any[];
    labInfo?: {
        name: string;
        address: string;
        phone: string;
    };
}

export const PatientReport = React.forwardRef<HTMLDivElement, PatientReportProps>(({ order, results, tests, labInfo }, ref) => {
    // Default Lab Info
    const lab = labInfo || {
        name: "Dx Clinical Laboratory",
        address: "123 Medical Center Dr, Suite 100, Health City",
        phone: "(555) 123-4567"
    };

    return (
        <div ref={ref} className="p-8 bg-white text-slate-900 max-w-[210mm] mx-auto hidden print:block print:w-full print:max-w-none">
            {/* PRELIMINARY/FINAL BANNER - APHL 2019 Requirement */}
            {order.status !== 'Completed' && (
                <div className="bg-red-600 text-white text-center py-4 mb-4 -mx-8 -mt-8 print:m-0">
                    <span className="text-2xl font-bold tracking-widest">⚠️ PRELIMINARY REPORT - NOT FOR CLINICAL USE ⚠️</span>
                </div>
            )}
            {order.status === 'Completed' && (
                <div className="bg-green-700 text-white text-center py-2 mb-4 -mx-8 -mt-8 print:m-0">
                    <span className="text-lg font-bold tracking-wider">✓ FINAL REPORT - CLINICALLY VERIFIED</span>
                </div>
            )}

            {/* Header */}
            <div className="border-b-2 border-slate-800 pb-6 mb-8 flex justify-between items-start">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-2">{lab.name}</h1>
                    <p className="text-sm text-slate-500">{lab.address}</p>
                    <p className="text-sm text-slate-500">{lab.phone}</p>
                </div>
                <div className="text-right">
                    <div className={`p-3 rounded ${order.status === 'Completed' ? 'bg-green-100' : 'bg-amber-100'}`}>
                        <p className="text-xs text-slate-500 uppercase font-semibold">Report Status</p>
                        <p className={`text-xl font-bold ${order.status === 'Completed' ? 'text-green-800' : 'text-amber-800'}`}>
                            {order.status === 'Completed' ? 'FINAL' : 'PRELIMINARY'}
                        </p>
                    </div>
                </div>
            </div>

            {/* Patient & Order Info */}
            <div className="grid grid-cols-2 gap-8 mb-8 text-sm">
                <div>
                    <h3 className="text-xs uppercase font-bold text-slate-500 mb-2 border-b pb-1">Patient Information</h3>
                    <div className="grid grid-cols-3 gap-2 py-1">
                        <span className="text-slate-500">Name:</span>
                        <span className="col-span-2 font-semibold">John Doe (Mock)</span> {/* In real app, fetch patient details */}
                    </div>
                    <div className="grid grid-cols-3 gap-2 py-1">
                        <span className="text-slate-500">ID / MRN:</span>
                        <span className="col-span-2 font-mono">{order.patientId}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 py-1">
                        <span className="text-slate-500">Accession:</span>
                        <span className="col-span-2 font-mono">{order.accessionNumber}</span>
                    </div>
                </div>
                <div>
                    <h3 className="text-xs uppercase font-bold text-slate-500 mb-2 border-b pb-1">Order Details</h3>
                    <div className="grid grid-cols-3 gap-2 py-1">
                        <span className="text-slate-500">Received:</span>
                        <span className="col-span-2">{formatDateTime(order.timestamp)}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 py-1">
                        <span className="text-slate-500">Reported:</span>
                        <span className="col-span-2">{formatDateTime(new Date().toISOString())}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 py-1">
                        <span className="text-slate-500">Physician:</span>
                        <span className="col-span-2">{order.orderingPhysician || 'Dr. House'}</span>
                    </div>
                </div>
            </div>

            {/* Results Table */}
            <div className="mb-8">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b-2 border-slate-200">
                            <th className="text-left py-2 font-bold text-slate-700 w-1/3">Test Name</th>
                            <th className="text-left py-2 font-bold text-slate-700">Result</th>
                            <th className="text-left py-2 font-bold text-slate-700">Units</th>
                            <th className="text-left py-2 font-bold text-slate-700">Ref. Range</th>
                            <th className="text-left py-2 font-bold text-slate-700">Flag</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(order.testIds || []).map((testId: string) => {
                            const test = tests.find(t => t.id === testId);
                            const val = results?.results?.[testId];
                            if (!test || !val) return null;

                            // Handle both string and object referenceRange formats
                            let flag = "";
                            let refRangeText = "";
                            try {
                                const refRange = test.referenceRange;
                                let min: number, max: number;

                                if (typeof refRange === 'object' && refRange !== null) {
                                    // New structured format: { min, max, text, ... }
                                    min = refRange.min;
                                    max = refRange.max;
                                    refRangeText = refRange.text || `${min}-${max}`;
                                } else if (typeof refRange === 'string') {
                                    // Legacy string format: "min-max"
                                    const parts = refRange.split('-').map(Number);
                                    min = parts[0];
                                    max = parts[1];
                                    refRangeText = refRange;
                                } else {
                                    refRangeText = 'N/A';
                                    min = NaN;
                                    max = NaN;
                                }

                                const numVal = parseFloat(val);
                                if (!isNaN(min) && !isNaN(max) && !isNaN(numVal)) {
                                    if (numVal < min) flag = "L";
                                    if (numVal > max) flag = "H";
                                }
                            } catch (e) { refRangeText = 'N/A'; }

                            return (
                                <tr key={testId} className="border-b border-slate-100">
                                    <td className="py-3 font-medium">{test.name}</td>
                                    <td className="py-3 font-bold">{val}</td>
                                    <td className="py-3 text-slate-500">{test.units}</td>
                                    <td className="py-3 text-slate-500">{refRangeText}</td>
                                    <td className={`py-3 font-bold ${flag === 'H' || flag === 'L' ? 'text-red-600' : ''}`}>{flag}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Comments */}
            {results?.notes && (
                <div className="mb-8 p-4 bg-slate-50 rounded border border-slate-200">
                    <h3 className="text-xs uppercase font-bold text-slate-500 mb-2">Report Notes</h3>
                    <p className="whitespace-pre-wrap">{results.notes}</p>
                </div>
            )}

            {/* Footer */}
            {/* Footer with Validation and QR */}
            <div className="mt-auto pt-8 border-t-2 border-slate-800 flex justify-between items-end">
                <div className="text-xs text-slate-500 max-w-md">
                    <p className="font-bold mb-1">Laboratory Director: Dr. A. Smith, PhD, FACB</p>
                    <p>Generated by Dx LIS (v2.0)</p>
                    <p>ISO 15189:2012 Certified Laboratory | CLIA #99D0999999</p>
                    <p className="mt-2 italic">Disclaimer: Results relate only to the items tested. This report shall not be reproduced except in full without written approval of the laboratory. Measurement uncertainty available upon request.</p>
                </div>

                <div className="flex flex-col items-end gap-4">
                    {/* QR Code for Verification */}
                    <img
                        src={`https://api.qrserver.com/v1/create-qr-code/?size=100x100&data=MEDILAB-${order.accessionNumber}`}
                        alt="Verification QR"
                        className="w-24 h-24 border border-slate-200"
                    />

                    <div className="text-center">
                        <div className="h-12 border-b border-slate-400 w-48 mb-2 flex items-end justify-center">
                            <span className="font-script text-2xl text-slate-600 italic mb-1">{results?.performedBy || 'System'}</span>
                        </div>
                        <p className="text-xs uppercase font-bold text-slate-500">Authorized Signatory</p>
                    </div>
                </div>
            </div>

            <div className="text-center text-[10px] text-slate-400 mt-4">
                *** End of Report ***
            </div>
        </div>
    );
});

PatientReport.displayName = "PatientReport";
