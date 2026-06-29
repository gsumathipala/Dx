import React from 'react';
import { formatDateTime } from '@/lib/utils';

// Props: order (with results), tests (definitions)
export const CoaReport = React.forwardRef<HTMLDivElement, { order: any, tests: any[], results: any }>(({ order, tests, results }, ref) => {
    if (!order) return null;

    return (
        <div ref={ref} className="p-8 bg-white text-slate-900 font-sans max-w-[210mm] mx-auto min-h-[297mm] text-sm leading-relaxed" style={{ printColorAdjust: 'exact', WebkitPrintColorAdjust: 'exact' }}>
            {/* Header */}
            <div className="flex justify-between items-start border-b-4 border-slate-900 pb-6 mb-8">
                <div>
                    <h1 className="text-3xl font-black tracking-tighter text-slate-900">CERTIFICATE OF ANALYSIS</h1>
                    <p className="text-slate-500 font-medium uppercase tracking-widest text-xs mt-1">ISO 17025 Accredited Laboratory</p>
                </div>
                <div className="text-right">
                    <h2 className="font-bold text-xl">Dx</h2>
                    <p className="text-xs text-slate-500">
                        123 Science Park Drive<br />
                        Innovation City, ST 54321<br />
                        Tel: +1 (555) 0199-8888
                    </p>
                </div>
            </div>

            {/* Sample Information Grid */}
            <div className="bg-slate-50 border border-slate-200 p-6 mb-8 rounded-sm">
                <div className="grid grid-cols-2 gap-y-4 gap-x-12">
                    <div>
                        <span className="block text-[10px] uppercase text-slate-500 font-bold tracking-wider mb-0.5">Product / Sample Name</span>
                        <div className="font-bold text-lg">{order.patientId || 'Batch Sample'}</div>
                    </div>
                    <div>
                        <span className="block text-[10px] uppercase text-slate-500 font-bold tracking-wider mb-0.5">Control / Lot Number</span>
                        <div className="font-mono font-bold">{order.accessionNumber}</div>
                    </div>
                    <div>
                        <span className="block text-[10px] uppercase text-slate-500 font-bold tracking-wider mb-0.5">Date of Manufacture / Receipt</span>
                        <div>{formatDateTime(order.timestamp)}</div>
                    </div>
                    <div>
                        <span className="block text-[10px] uppercase text-slate-500 font-bold tracking-wider mb-0.5">Date of Analysis</span>
                        <div>{formatDateTime(new Date().toISOString())}</div>
                    </div>
                </div>
            </div>

            {/* Analysis Results Table */}
            <table className="w-full mb-12 border-collapse text-sm">
                <thead>
                    <tr className="border-b-2 border-slate-900">
                        <th className="text-left py-3 font-bold uppercase text-xs w-1/3">Test Parameter</th>
                        <th className="text-left py-3 font-bold uppercase text-xs w-1/4">Specification</th>
                        <th className="text-left py-3 font-bold uppercase text-xs w-1/4">Result</th>
                        <th className="text-right py-3 font-bold uppercase text-xs">Disposition</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                    {(order.testIds || []).map((testId: string) => {
                        const testDef = tests.find(t => t.id === testId);
                        const value = results?.results?.[testId] || 'N/A';

                        // Fake spec logic for demo
                        const spec = testDef?.units === 'g/dL' ? '12.0 - 18.0' : 'N/A';
                        const isNumeric = !isNaN(parseFloat(value));
                        let passed = true;

                        // Simple dummy check for Pass/Fail
                        if (isNumeric && spec !== 'N/A') {
                            const val = parseFloat(value);
                            passed = val >= 12.0 && val <= 18.0;
                        }

                        return (
                            <tr key={testId}>
                                <td className="py-4 align-top">
                                    <div className="font-bold">{testDef?.name || testId}</div>
                                    <div className="text-xs text-slate-500">{testDef?.category || 'General'}</div>
                                </td>
                                <td className="py-4 align-top font-mono text-slate-600">
                                    {spec} {testDef?.units}
                                </td>
                                <td className="py-4 align-top font-bold text-slate-900">
                                    {value} <span className="text-xs font-normal text-slate-500">{testDef?.units}</span>
                                </td>
                                <td className="py-4 align-top text-right">
                                    {spec !== 'N/A' ? (
                                        <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest ${passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                            {passed ? 'PASS' : 'FAIL'}
                                        </span>
                                    ) : (
                                        <span className="text-slate-400 text-xs">-</span>
                                    )}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>

            {/* Footer / Certification */}
            <div className="mt-auto pt-12 border-t border-slate-200">
                <div className="flex justify-between items-end">
                    <div className="w-1/2">
                        <p className="text-xs text-slate-500 mb-6 italic">
                            This report is electronically generated and valid without signature.
                            The results relate only to the items tested.
                        </p>
                        <div className="h-16 w-48 border-b border-slate-900 mb-2 relative">
                            {/* Signature placeholder */}
                            <div className="absolute bottom-2 font-handwriting text-2xl text-slate-800 font-bold">dx_system</div>
                        </div>
                        <p className="font-bold text-xs uppercase tracking-wider">Authorized Release</p>
                        <p className="text-xs text-slate-500">Quality Assurance Manager</p>
                    </div>
                    <div className="text-right">
                        <div className="inline-block p-4 border-2 border-slate-900 rounded opacity-80 rotate-[-10deg]">
                            <span className="block text-2xl font-black text-slate-900 uppercase">Released</span>
                            <span className="block text-[10px] font-bold uppercase tracking-widest text-slate-600">{formatDateTime(new Date().toISOString())}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
});
CoaReport.displayName = 'CoaReport';
