"use client";

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { formatDateTime } from '@/lib/utils';
import { useAuth } from '@/context/AuthContext';

export default function Patient360Page() {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<any[]>([]);
    const [selectedPatient, setSelectedPatient] = useState<any>(null);
    const [history, setHistory] = useState<any>(null); // { patient, orders, results, micro }
    const [activeTab, setActiveTab] = useState('timeline');

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        const res = await fetch(`/api/patient-360?q=${query}`);
        setResults(await res.json());
        setSelectedPatient(null);
        setHistory(null);
    };

    const selectPatient = async (patient: any) => {
        setSelectedPatient(patient);
        const res = await fetch(`/api/patient-360?id=${patient.id}`);
        setHistory(await res.json());
        setResults([]);
    };

    const getResultForOrder = (orderId: string) => {
        if (!history) return null;
        return history.results.find((r: any) => r.orderId === orderId);
    };

    const getMicroForOrder = (orderId: string) => {
        if (!history) return null;
        return history.micro.find((m: any) => m.orderId === orderId);
    };

    return (
        <div className="space-y-6 min-h-[500px] flex flex-col">
            {/* Search Bar */}
            {!selectedPatient && (
                <div className="flex flex-col items-center justify-center flex-1">
                    <h1 className="text-4xl font-bold text-slate-800 mb-8">Patient 360° (Beaker)</h1>
                    <Card className="w-full max-w-2xl">
                        <form onSubmit={handleSearch} className="flex gap-4">
                            <input
                                className="input-field text-lg"
                                placeholder="Search Patient Name or MRN..."
                                value={query}
                                onChange={e => setQuery(e.target.value)}
                                autoFocus
                            />
                            <button className="btn-primary text-lg px-8">Search</button>
                        </form>
                        {results.length > 0 && (
                            <div className="mt-4 border-t pt-4 space-y-2">
                                {results.map(p => (
                                    <div key={p.id} onClick={() => selectPatient(p)} className="p-3 hover:bg-slate-50 border rounded cursor-pointer flex justify-between items-center">
                                        <div>
                                            <p className="font-bold text-lg text-slate-900">{p.name}</p>
                                            <p className="text-sm text-slate-500">MRN: {p.hospitalNumber} | DOB: {p.dob}</p>
                                        </div>
                                        <span className="text-blue-600 font-bold">&rarr;</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </Card>
                </div>
            )}

            {/* Patient Chart View */}
            {selectedPatient && history && (
                <>
                    {/* Patient Header (Sticky) */}
                    <div className="bg-white border-b shadow-sm p-4 -mx-6 -mt-6 px-8 flex justify-between items-start sticky top-0 z-10">
                        <div className="flex items-center gap-4">
                            <div className="w-16 h-16 bg-slate-200 rounded-full flex items-center justify-center text-2xl font-bold text-slate-500">
                                {selectedPatient.name.charAt(0)}
                            </div>
                            <div>
                                <h1 className="text-2xl font-bold text-slate-900">{selectedPatient.name}</h1>
                                <div className="flex gap-4 text-sm text-slate-600 mt-1">
                                    <span><span className="font-bold">MRN:</span> {selectedPatient.hospitalNumber}</span>
                                    <span><span className="font-bold">DOB:</span> {selectedPatient.dob}</span>
                                    <span><span className="font-bold">Sex:</span> {selectedPatient.gender}</span>
                                </div>
                            </div>
                        </div>
                        <button onClick={() => { setSelectedPatient(null); setQuery(''); }} className="text-slate-500 hover:text-slate-800 underline text-sm">
                            Close Chart
                        </button>
                    </div>

                    {/* Tabs */}
                    <div className="flex gap-4 border-b">
                        <button
                            onClick={() => setActiveTab('timeline')}
                            className={`pb-2 font-bold ${activeTab === 'timeline' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-slate-500'}`}
                        >
                            History & Timeline
                        </button>
                        <button
                            onClick={() => setActiveTab('outstanding')}
                            className={`pb-2 font-bold ${activeTab === 'outstanding' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-slate-500'}`}
                        >
                            Outstanding List ({history.orders.filter((o: any) => o.status !== 'Completed').length})
                        </button>
                    </div>

                    {/* Content */}
                    <div className="flex-1 overflow-y-auto pb-8">
                        {activeTab === 'timeline' && (
                            <div className="space-y-6 max-w-4xl">
                                {history.orders.length === 0 && <p className="text-slate-400 p-4">No history found.</p>}
                                {history.orders.map((order: any) => {
                                    const result = getResultForOrder(order.id);
                                    const micro = getMicroForOrder(order.id);

                                    return (
                                        <Card key={order.id} className="relative overflow-visible">
                                            {/* Timeline Connector */}
                                            <div className="absolute -left-3 top-6 w-3 h-3 rounded-full bg-slate-300"></div>

                                            <div className="flex justify-between items-start mb-4 border-b pb-2">
                                                <div>
                                                    <p className="font-bold text-lg text-slate-800">{formatDateTime(order.timestamp)}</p>
                                                    <p className="text-sm text-slate-500 font-mono">ACC: {order.accessionNumber}</p>
                                                </div>
                                                <StatusBadge status={order.status} />
                                            </div>

                                            {/* Tests Requested */}
                                            <div className="mb-4">
                                                <p className="text-xs font-bold uppercase text-slate-400 mb-1">Tests</p>
                                                <div className="flex flex-wrap gap-2">
                                                    {order.testIds.map((t: string) => <Badge key={t}>{t}</Badge>)}
                                                </div>
                                            </div>

                                            {/* Results Preview */}
                                            {result && (
                                                <div className="bg-slate-50 p-3 rounded border">
                                                    <p className="text-xs font-bold uppercase text-slate-400 mb-2">Results</p>
                                                    <div className="grid grid-cols-2 gap-4 text-sm">
                                                        {Object.entries(result.values.results || {}).map(([key, val]: any) => (
                                                            <div key={key} className="flex justify-between border-b border-slate-200 pb-1">
                                                                <span className="font-medium">{key}</span>
                                                                <span className="font-bold">{val}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Micro Preview */}
                                            {micro && (
                                                <div className="mt-2 bg-teal-50 p-3 rounded border border-teal-100">
                                                    <p className="text-xs font-bold uppercase text-teal-600 mb-1">Microbiology</p>
                                                    <p className="text-sm font-bold text-teal-900">{micro.organism || 'Pending ID'}</p>
                                                    <p className="text-xs text-teal-700">{micro.growth}</p>
                                                </div>
                                            )}
                                        </Card>
                                    );
                                })}
                            </div>
                        )}

                        {activeTab === 'outstanding' && (
                            <div className="space-y-4">
                                <Card className="bg-amber-50 border-amber-200">
                                    <h3 className="text-amber-800 font-bold mb-2">Pending Actions</h3>
                                    <ul className="list-disc ml-5 text-amber-900">
                                        {history.orders.filter((o: any) => o.status !== 'Completed').map((o: any) => (
                                            <li key={o.id}>
                                                <span className="font-bold">{o.accessionNumber}</span>: Ordered on {new Date(o.timestamp).toLocaleDateString()}. Status: {o.status}.
                                            </li>
                                        ))}
                                        {history.orders.filter((o: any) => o.status !== 'Completed').length === 0 && <li>No outstanding orders.</li>}
                                    </ul>
                                </Card>
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}
