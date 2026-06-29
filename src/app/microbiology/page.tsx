"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useAuth } from '@/context/AuthContext';
import { Settings, Trash2, Plus, X } from 'lucide-react';

export default function MicrobiologyPage() {
    const [orders, setOrders] = useState<any[]>([]);
    const [selectedOrder, setSelectedOrder] = useState<any>(null);
    const [workup, setWorkup] = useState<any>({
        dayReadings: { 'Day 1': '', 'Day 2': '', 'Day 3': '' },
        organism: '',
        growth: '',
        sensitivity: {},
        epiAlerts: []
    });

    const { user } = useAuth();
    const canManage = user?.role === 'admin' || user?.role === 'manager';

    const [antibiotics, setAntibiotics] = useState<string[]>([]);
    const [showAbxModal, setShowAbxModal] = useState(false);
    const [newAbxName, setNewAbxName] = useState('');

    const loadConfig = () => {
        fetch('/api/microbiology?type=config')
            .then(r => r.json())
            .then(data => {
                if (data.antibiotics && data.antibiotics.length > 0) {
                    setAntibiotics(data.antibiotics);
                } else {
                    // Fallback
                    setAntibiotics(['Amoxicillin', 'Gentamicin', 'Ciprofloxacin', 'Vancomycin', 'Meropenem']);
                }
            });
    };

    const loadOrders = () => {
        fetch('/api/orders').then(r => r.json()).then(data => {
            // Filter assuming any order could be micro for demo
            setOrders(data.filter((o: any) => o.status !== 'Completed'));
        });
    };

    useEffect(() => {
        loadOrders();
        loadConfig();
    }, []);

    useEffect(() => {
        if (selectedOrder) {
            fetch(`/api/microbiology?orderId=${selectedOrder.id}`)
                .then(r => r.json())
                .then(data => {
                    if (data && data.length > 0) {
                        setWorkup(data[0]);
                    } else {
                        // Reset
                        setWorkup({
                            dayReadings: { 'Day 1': '', 'Day 2': '', 'Day 3': '' },
                            organism: '',
                            growth: '',
                            sensitivity: {},
                            epiAlerts: []
                        });
                    }
                });
        }
    }, [selectedOrder]);

    const handleSave = async (finalize = false) => {
        const payload = {
            orderId: selectedOrder.id,
            ...workup,
            finalReport: finalize
        };

        await fetch('/api/microbiology', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        // Refresh alert check
        const res = await fetch(`/api/microbiology?orderId=${selectedOrder.id}`);
        const data = await res.json();
        if (data[0]) setWorkup(data[0]);

        alert('Workup Saved' + (finalize ? ' & Posted to Report' : ''));
    };

    const toggleSens = (abx: string) => {
        const current = workup.sensitivity[abx];
        const next = current === 'S' ? 'I' : current === 'I' ? 'R' : current === 'R' ? '' : 'S';
        setWorkup({
            ...workup,
            sensitivity: { ...workup.sensitivity, [abx]: next }
        });
    };

    const handleAddAbx = async () => {
        if (!newAbxName) return;
        const updated = [...antibiotics, newAbxName];
        await saveConfig(updated);
        setNewAbxName('');
    };

    const handleRemoveAbx = async (abx: string) => {
        if (!confirm(`Remove ${abx} from panel?`)) return;
        const updated = antibiotics.filter(a => a !== abx);
        await saveConfig(updated);
    };

    const saveConfig = async (list: string[]) => {
        setAntibiotics(list);
        await fetch('/api/microbiology', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'update_config', antibiotics: list })
        });
    };

    return (
        <div className="flex gap-6 min-h-[500px]">
            {/* Bench Worklist */}
            <div className="w-1/4 flex flex-col gap-4">
                <Card className="flex-1 p-0 overflow-hidden" title="Bench Worklist">
                    <div className="overflow-y-auto p-2 space-y-2">
                        {orders.map(o => (
                            <div key={o.id} onClick={() => setSelectedOrder(o)} className={`p-3 rounded border cursor-pointer border-l-4 ${selectedOrder?.id === o.id ? 'bg-teal-50 border-l-teal-500' : 'bg-white border-l-slate-300'}`}>
                                <div className="font-bold font-mono">{o.accessionNumber}</div>
                                <div className="text-xs text-slate-500">Specimen</div>
                            </div>
                        ))}
                    </div>
                </Card>
            </div>

            {/* Workbench */}
            <div className="flex-1 overflow-y-auto">
                {selectedOrder ? (
                    <div className="space-y-6">
                        {/* Header */}
                        <div className="flex justify-between items-center bg-white p-4 rounded-lg shadow-sm border">
                            <div>
                                <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                                    🧫 Culture Workbench
                                    {canManage && (
                                        <button onClick={() => setShowAbxModal(true)} className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-2 py-1 rounded border flex items-center gap-1">
                                            <Settings className="w-3 h-3" /> Panel
                                        </button>
                                    )}
                                </h1>
                                <p className="text-sm text-slate-500">Accession: <span className="font-mono font-bold">{selectedOrder.accessionNumber}</span></p>
                            </div>
                            <div className="flex gap-2">
                                <button onClick={() => handleSave(false)} className="btn-secondary">Save Progress</button>
                                <button onClick={() => handleSave(true)} className="btn-primary">Finalize Report</button>
                            </div>
                        </div>

                        {/* Infection Control Alert Banner */}
                        {workup.epiAlerts?.map((alert: string, i: number) => (
                            <div key={i} className="bg-red-600 text-white p-4 rounded-lg font-bold text-center animate-pulse shadow-lg">
                                ☣️ EPIDEMIOLOGY ALERT: {alert} ☣️
                            </div>
                        ))}

                        <div className="grid grid-cols-2 gap-6">
                            {/* Plate Readings */}
                            <Card title="Plate Readings">
                                <div className="space-y-4">
                                    {['Day 1', 'Day 2', 'Day 3'].map(day => (
                                        <div key={day} className="flex items-center gap-4">
                                            <label className="w-16 font-bold text-sm text-slate-500">{day}</label>
                                            <input
                                                className="input-field"
                                                placeholder="Growth Observation..."
                                                value={workup.dayReadings[day] || ''}
                                                onChange={e => setWorkup({ ...workup, dayReadings: { ...workup.dayReadings, [day]: e.target.value } })}
                                            />
                                        </div>
                                    ))}
                                </div>
                            </Card>

                            {/* Identification */}
                            <Card title="Identification">
                                <div className="space-y-4">
                                    <div>
                                        <label className="label">Observed Growth</label>
                                        <select className="input-field" value={workup.growth} onChange={e => setWorkup({ ...workup, growth: e.target.value })}>
                                            <option value="">-- Select --</option>
                                            <option>No Growth</option>
                                            <option>Scanty Growth</option>
                                            <option>Moderate Growth</option>
                                            <option>Heavy Growth</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="label">Organism ID</label>
                                        <select className="input-field" value={workup.organism} onChange={e => setWorkup({ ...workup, organism: e.target.value })}>
                                            <option value="">-- Pending --</option>
                                            <option value="E. coli">E. coli</option>
                                            <option value="S. aureus">S. aureus</option>
                                            <option value="S. aureus (MRSA)">S. aureus (MRSA)</option>
                                            <option value="P. aeruginosa">P. aeruginosa</option>
                                            <option value="Enterococcus">Enterococcus</option>
                                            <option value="Enterococcus (VRE)">Enterococcus (VRE)</option>
                                            <option value="Candida albicans">Candida albicans</option>
                                        </select>
                                    </div>
                                </div>
                            </Card>
                        </div>

                        {/* Sensitivity Grid (AST) */}
                        <Card title="Antibiotic Susceptibility Testing (AST)">
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                {antibiotics.map(abx => {
                                    const res = workup.sensitivity[abx];
                                    let color = 'bg-slate-100 text-slate-500';
                                    if (res === 'S') color = 'bg-green-100 text-green-700 border-green-300';
                                    if (res === 'I') color = 'bg-yellow-100 text-yellow-700 border-yellow-300';
                                    if (res === 'R') color = 'bg-red-100 text-red-700 border-red-300';

                                    return (
                                        <div key={abx} className="flex justify-between items-center p-3 border rounded">
                                            <span className="font-bold text-sm text-slate-700">{abx}</span>
                                            <button
                                                onClick={() => toggleSens(abx)}
                                                className={`w-8 h-8 rounded-full font-bold flex items-center justify-center border transition-colors ${color}`}
                                            >
                                                {res || '-'}
                                            </button>
                                        </div>
                                    );
                                })}
                            </div>
                            <p className="text-xs text-slate-400 mt-4 text-center">Click circle to toggle: S (Sensitive) &rarr; I (Intermediate) &rarr; R (Resistant)</p>
                        </Card>
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center h-full text-slate-400">
                        <div className="text-6xl mb-4">🧫</div>
                        <p>Select a culture from the bench</p>
                    </div>
                )}
            </div>

            {/* Manage Antibiotics Modal */}
            {showAbxModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-96 p-4 bg-white shadow-xl max-h-[80vh] flex flex-col" title="Manage AST Panel">
                        <div className="flex-1 overflow-y-auto space-y-2 p-2">
                            {antibiotics.map(abx => (
                                <div key={abx} className="flex justify-between items-center p-2 bg-slate-50 rounded border">
                                    <span className="font-medium">{abx}</span>
                                    <button onClick={() => handleRemoveAbx(abx)} className="text-red-500 hover:text-red-700">
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            ))}
                        </div>
                        <div className="pt-4 border-t mt-2 flex gap-2">
                            <input
                                className="flex-1 border rounded px-2 py-1"
                                placeholder="New Antibiotic..."
                                value={newAbxName}
                                onChange={e => setNewAbxName(e.target.value)}
                            />
                            <button onClick={handleAddAbx} className="bg-indigo-600 text-white px-3 py-1 rounded hover:bg-indigo-700">
                                <Plus className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="pt-2 flex justify-end">
                            <button onClick={() => setShowAbxModal(false)} className="text-sm text-slate-500 hover:text-slate-800">Close</button>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
}
