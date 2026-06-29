"use client";

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Card } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/Badge';
import { formatDateTime } from '@/lib/utils';

export default function WorksheetsPage() {
    const { user } = useAuth();
    const [worksheets, setWorksheets] = useState<any[]>([]);
    const [orders, setOrders] = useState<any[]>([]);
    const [selectedWorksheet, setSelectedWorksheet] = useState<any>(null);
    const [isCreating, setIsCreating] = useState(false);

    // New Worksheet Form
    const [newWsName, setNewWsName] = useState('');
    const [newWsInstrument, setNewWsInstrument] = useState('Chemistry Analyzer 1');

    // Header editing
    const [isEditingHeader, setIsEditingHeader] = useState(false);
    const [headerForm, setHeaderForm] = useState({ name: '', instrument: '' });

    // Reset edit mode when selection changes
    useEffect(() => {
        setIsEditingHeader(false);
    }, [selectedWorksheet?.id]);

    const loadData = async () => {
        const [wsRes, ordersRes] = await Promise.all([
            fetch('/api/worksheets').then(r => r.json()),
            fetch('/api/orders').then(r => r.json())
        ]);
        setWorksheets(wsRes);
        setOrders(ordersRes);
    };

    useEffect(() => { loadData(); }, []);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        const res = await fetch('/api/worksheets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: newWsName,
                instrument: newWsInstrument,
                sampleIds: [],
                createdBy: user?.username
            })
        });

        if (res.ok) {
            setIsCreating(false);
            setNewWsName('');
            loadData();
        }
    };

    const updateWorksheet = async (updates: any) => {
        if (!selectedWorksheet) return;
        const res = await fetch('/api/worksheets', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: selectedWorksheet.id, updates })
        });
        if (res.ok) {
            const updated = await res.json();
            setSelectedWorksheet(updated);
            loadData();
        }
    };

    const handleAddSample = (orderId: string) => {
        const currentIds = selectedWorksheet.sampleIds || [];
        if (currentIds.includes(orderId)) return;
        updateWorksheet({ sampleIds: [...currentIds, orderId] });
    };

    const handleRemoveSample = (orderId: string) => {
        const currentIds = selectedWorksheet.sampleIds || [];
        updateWorksheet({ sampleIds: currentIds.filter((id: string) => id !== orderId) });
    };

    const handleDeleteWorksheet = async () => {
        if (!selectedWorksheet || !confirm(`Delete worksheet '${selectedWorksheet.name}'?`)) return;
        const res = await fetch(`/api/worksheets?id=${selectedWorksheet.id}`, { method: 'DELETE' });
        if (res.ok) {
            setSelectedWorksheet(null);
            loadData();
        }
    };

    const handleStatusUpdate = (newStatus: string) => {
        updateWorksheet({ status: newStatus });
    };

    return (
        <div className="flex gap-6" style={{ minHeight: '500px' }}>
            {/* Sidebar List */}
            <div className="w-1/3 flex flex-col gap-4">
                <Card className="flex flex-col p-0 overflow-hidden" style={{ maxHeight: 'calc(100vh - 10rem)' }}>
                    <div className="p-4 border-b bg-slate-50 flex justify-between items-center flex-shrink-0">
                        <h2 className="font-bold text-lg text-slate-800">Worksheets</h2>
                        <button onClick={() => setIsCreating(true)} className="btn-primary text-xs">+ New Batch</button>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                        {worksheets.map(ws => (
                            <div
                                key={ws.id}
                                onClick={() => setSelectedWorksheet(ws)}
                                className={`p-4 rounded border cursor-pointer hover:bg-slate-50 ${selectedWorksheet?.id === ws.id ? 'bg-blue-50 border-blue-200' : ''}`}
                            >
                                <div className="flex justify-between font-bold text-slate-800">
                                    <span>{ws.name}</span>
                                    <span className="text-xs bg-slate-200 px-2 py-0.5 rounded">{ws.status}</span>
                                </div>
                                <div className="text-xs text-slate-500 mt-1">{ws.instrument}</div>
                                <div className="text-xs text-slate-400">{formatDateTime(ws.createdAt)}</div>
                            </div>
                        ))}
                    </div>
                </Card>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {isCreating ? (
                    <Card>
                        <h2 className="text-xl font-bold mb-4">Create New Worksheet</h2>
                        <form onSubmit={handleCreate} className="space-y-4">
                            <div>
                                <label className="label">Batch Name / ID</label>
                                <input className="input-field" required value={newWsName} onChange={e => setNewWsName(e.target.value)} placeholder="e.g. Chem Run 2024-10-25 A" />
                            </div>
                            <div>
                                <label className="label">Instrument</label>
                                <select className="input-field" value={newWsInstrument} onChange={e => setNewWsInstrument(e.target.value)}>
                                    <option>Chemistry Analyzer 1</option>
                                    <option>Chemistry Analyzer 2</option>
                                    <option>Immunoassay System</option>
                                    <option>Hematology Counter</option>
                                </select>
                            </div>
                            <div className="flex justify-end gap-2">
                                <button type="button" onClick={() => setIsCreating(false)} className="btn-secondary">Cancel</button>
                                <button type="submit" className="btn-primary">Create Worksheet</button>
                            </div>
                        </form>
                    </Card>
                ) : selectedWorksheet ? (
                    <Card className="flex flex-col p-0 overflow-hidden" style={{ maxHeight: 'calc(100vh - 10rem)' }}>
                        <div className="p-6 border-b bg-slate-50 flex justify-between items-center flex-shrink-0">
                            <div className="flex-1 mr-4">
                                {isEditingHeader ? (
                                    <div className="space-y-2">
                                        <input
                                            className="input-field font-bold text-xl"
                                            value={headerForm.name}
                                            onChange={e => setHeaderForm({ ...headerForm, name: e.target.value })}
                                            autoFocus
                                        />
                                        <div className="flex gap-2">
                                            <select
                                                className="input-field text-sm w-auto"
                                                value={headerForm.instrument}
                                                onChange={e => setHeaderForm({ ...headerForm, instrument: e.target.value })}
                                            >
                                                <option>Chemistry Analyzer 1</option>
                                                <option>Chemistry Analyzer 2</option>
                                                <option>Immunoassay System</option>
                                                <option>Hematology Counter</option>
                                            </select>
                                            <button
                                                onClick={() => {
                                                    updateWorksheet(headerForm);
                                                    setIsEditingHeader(false);
                                                }}
                                                className="bg-green-600 text-white px-3 py-1 rounded text-xs"
                                            >
                                                Save
                                            </button>
                                            <button onClick={() => setIsEditingHeader(false)} className="bg-gray-200 text-gray-700 px-3 py-1 rounded text-xs">Cancel</button>
                                        </div>
                                    </div>
                                ) : (
                                    <>
                                        <div className="flex items-center gap-2 group">
                                            <h1 className="text-2xl font-bold text-slate-900">{selectedWorksheet.name}</h1>
                                            <button
                                                onClick={() => {
                                                    setHeaderForm({ name: selectedWorksheet.name, instrument: selectedWorksheet.instrument });
                                                    setIsEditingHeader(true);
                                                }}
                                                className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-blue-600"
                                            >
                                                ✏️
                                            </button>
                                        </div>
                                        <div className="flex gap-2 items-center mt-1">
                                            <p className="text-slate-500 text-sm">{selectedWorksheet.instrument}</p>
                                            <select
                                                className="text-xs border rounded p-1 bg-white"
                                                value={selectedWorksheet.status}
                                                onChange={(e) => handleStatusUpdate(e.target.value)}
                                            >
                                                <option>Open</option>
                                                <option>Closed</option>
                                                <option>Sent to Analyzer</option>
                                                <option>Completed</option>
                                            </select>
                                        </div>
                                    </>
                                )}
                            </div>
                            <div className="flex gap-2">
                                <button onClick={handleDeleteWorksheet} className="text-red-600 hover:bg-red-50 p-2 rounded" title="Delete Worksheet">🗑️</button>
                                <button className="btn-secondary">🖨️ Load List</button>
                                <button className="btn-primary">⬇️ Send</button>
                            </div>
                        </div>

                        <div className="p-6 overflow-y-auto flex-1">
                            <h3 className="font-bold text-slate-700 mb-2">Assigned Samples</h3>
                            {(!selectedWorksheet.sampleIds || selectedWorksheet.sampleIds.length === 0) ? (
                                <div className="text-slate-400 italic mb-6">No samples assigned yet.</div>
                            ) : (
                                <div className="mb-6 space-y-2">
                                    {orders.filter(o => selectedWorksheet.sampleIds?.includes(o.id)).map(order => (
                                        <div key={order.id} className="flex justify-between items-center p-3 bg-white border rounded shadow-sm">
                                            <div>
                                                <div className="font-mono font-bold">{order.accessionNumber}</div>
                                                <div className="text-xs text-slate-500">{order.testIds.join(', ')}</div>
                                            </div>
                                            <button onClick={() => handleRemoveSample(order.id)} className="text-red-500 hover:text-red-700 text-sm font-bold">Remove</button>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <div className="border-t pt-4">
                                <h3 className="font-bold text-slate-700 mb-2">Add Pending Samples</h3>
                                <div className="max-h-64 overflow-y-auto border rounded">
                                    <table className="w-full text-xs text-left">
                                        <thead className="bg-slate-100 sticky top-0">
                                            <tr>
                                                <th className="p-2">Accession</th>
                                                <th className="p-2">Tests</th>
                                                <th className="p-2">Action</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {orders.filter(o => o.status === 'Pending').map(order => (
                                                <tr key={order.id} className="border-b hover:bg-slate-50">
                                                    <td className="p-2 font-mono">{order.accessionNumber}</td>
                                                    <td className="p-2 truncate max-w-xs">{order.testIds.join(', ')}</td>
                                                    <td className="p-2">
                                                        <button onClick={() => handleAddSample(order.id)} className="text-blue-600 font-bold hover:underline">
                                                            + Add to Batch
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </Card>
                ) : (
                    <div className="flex-1 flex items-center justify-center text-slate-400">Select a worksheet or create new</div>
                )}
            </div>
        </div >
    );
}
