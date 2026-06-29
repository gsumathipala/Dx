"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Activity, Calendar, FileText, ChevronLeft, AlertCircle, Mail } from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

export default function PatientDetailPage() {
    const { id } = useParams();
    const router = useRouter();
    const [data, setData] = useState<any>(null);
    const [selectedTest, setSelectedTest] = useState<string>('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (id) loadHistory();
    }, [id]);

    const loadHistory = async () => {
        try {
            const res = await fetch(`/api/patients/${id}/history`);
            if (res.ok) {
                const result = await res.json();
                setData(result);
                // Default to first available test for trending
                if (result.history.length > 0) {
                    setSelectedTest(result.history[0].testName);
                }
            }
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    };

    if (loading) return <div className="p-8">Loading patient record...</div>;
    if (!data || !data.patient) return <div className="p-8">Patient not found.</div>;

    // Analytics Logic
    const getTrendData = (testName: string) => {
        return data.history
            .filter((r: any) => r.testName === testName)
            .map((r: any) => ({
                date: new Date(r.performedAt).toLocaleDateString(),
                value: parseFloat(r.value),
                flag: r.flags
            }));
    };

    const trendData = selectedTest ? getTrendData(selectedTest) : [];

    // Unique tests for dropdown
    const availableTests = Array.from(new Set(data.history.map((r: any) => r.testName)));

    return (
        <div className="space-y-6 max-w-6xl mx-auto">
            <Button variant="outline" className="pl-0 gap-2 border-none shadow-none hover:bg-transparent hover:text-primary-600" onClick={() => router.back()}>
                <ChevronLeft className="w-4 h-4" /> Back to List
            </Button>

            {/* HEADER - WHOLE PATIENT VIEW (Issue #34) */}
            <div className="flex justify-between items-start bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">{data.patient.name}</h1>
                    <div className="flex gap-6 mt-2 text-slate-500 text-sm">
                        <div className="flex items-center gap-2"><Calendar className="w-4 h-4" /> DOB: {data.patient.dateOfBirth}</div>
                        <div className="flex items-center gap-2 font-mono bg-slate-100 px-2 rounded">MRN: {data.patient.id}</div>
                        <div>Gender: {data.patient.gender}</div>
                    </div>
                </div>
                <div className="flex gap-2">
                    <Button className="bg-primary-600">Accession New Order</Button>
                </div>
            </div>

            {/* ANALYTICS - TREND GRAPH (Issue #36) */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card title="Longitudinal Analysis" className="lg:col-span-2">
                    <div className="mb-4 flex justify-between items-center">
                        <h3 className="font-semibold text-slate-700">Result Trends</h3>
                        <select
                            className="border p-1 rounded text-sm"
                            value={selectedTest}
                            onChange={(e) => setSelectedTest(e.target.value)}
                        >
                            {availableTests.map((t: any) => <option key={t} value={t}>{t}</option>)}
                            {availableTests.length === 0 && <option>No Data</option>}
                        </select>
                    </div>

                    {availableTests.length > 0 ? (
                        <div className="h-64 w-full bg-slate-50 rounded flex items-end p-4 gap-2 relative border border-slate-100">
                            {/* Simple CSS Bar Chart for robustness */}
                            {trendData.map((d: any, i: number) => {
                                // Simple scaling - assume max 200 for demo, normally would calculate max
                                const maxVal = Math.max(...trendData.map((t: any) => t.value)) || 100;
                                const height = (d.value / (maxVal * 1.2)) * 100;

                                return (
                                    <div key={i} className="flex-1 flex flex-col justify-end items-center group relative h-full">
                                        <div className="opacity-0 group-hover:opacity-100 absolute -top-10 bg-black text-white text-xs p-1 rounded z-10 whitespace-nowrap">
                                            {d.value} ({d.date})
                                        </div>
                                        <div
                                            className={`w-full max-w-[40px] rounded-t transition-all ${d.flag ? 'bg-red-400' : 'bg-primary-400'} hover:bg-primary-600`}
                                            style={{ height: `${height}%` }}
                                        ></div>
                                        <span className="text-[10px] text-slate-400 mt-1 rotate-45 origin-left truncate w-full">{d.date}</span>
                                    </div>
                                );
                            })}
                            {trendData.length === 0 && <div className="absolute inset-0 flex items-center justify-center text-slate-400">Select a test to view trends</div>}
                        </div>
                    ) : (
                        <div className="h-64 flex items-center justify-center text-slate-400 italic">
                            No historical results available for analysis.
                        </div>
                    )}
                </Card>

                {/* RECENT ACTIVITY */}
                <Card title="Recent Orders">
                    <div className="space-y-4">
                        {data.orders.slice(0, 5).map((o: any) => (
                            <div key={o.id} className="flex items-center justify-between p-3 bg-slate-50 rounded border border-slate-100">
                                <div>
                                    <div className="font-semibold text-sm">{o.accessionNumber || o.id}</div>
                                    <div className="text-xs text-slate-500">{new Date(o.timestamp || o.createdAt).toLocaleDateString()}</div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className={`text-xs px-2 py-1 rounded-full ${o.status === 'Completed' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>
                                        {o.status}
                                    </span>
                                    {o.status === 'Completed' && (
                                        <button
                                            onClick={async () => {
                                                if (!confirm(`Add Order ${o.id} to Email Queue?`)) return;
                                                const res = await fetch('/api/reporting/email', {
                                                    method: 'POST',
                                                    headers: { 'Content-Type': 'application/json' },
                                                    body: JSON.stringify({ action: 'ADD', orderId: o.id })
                                                });
                                                if (res.ok) alert('Added to Email Queue');
                                                else alert('Failed to add (might already be queued)');
                                            }}
                                            className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded bg-white border shadow-sm transition-colors"
                                            title="Queue Report for Email"
                                        >
                                            <Mail className="w-4 h-4" />
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                        {data.orders.length === 0 && <div className="text-slate-400 text-sm">No recent orders.</div>}
                    </div>
                </Card>
            </div>

            {/* FULL HISTORY TABLE (Issue #23) */}
            <Card title="Cumulative Result History">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50 text-slate-600 border-b">
                            <tr>
                                <th className="p-3">Date</th>
                                <th className="p-3">Test</th>
                                <th className="p-3">Value</th>
                                <th className="p-3">Unit</th>
                                <th className="p-3">Ref. Range</th>
                                <th className="p-3">Flags</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.history.map((r: any) => (
                                <tr key={r.id} className="border-b hover:bg-slate-50">
                                    <td className="p-3">{new Date(r.performedAt).toLocaleDateString()} {new Date(r.performedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                                    <td className="p-3 font-medium">{r.testName}</td>
                                    <td className="p-3 font-bold">{r.value}</td>
                                    <td className="p-3 text-slate-500">{r.unit}</td>
                                    <td className="p-3 text-slate-500">{r.referenceRange}</td>
                                    <td className="p-3">
                                        {r.flags && <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs font-bold">{r.flags}</span>}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </Card>
        </div>
    );
}
