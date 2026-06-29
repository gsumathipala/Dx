'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { AlertCircle, Plus, Trash2, Edit2, Save, X, Globe } from 'lucide-react';

interface Condition {
    id: string;
    name: string;
    organism: string;
    testIds: string[];
    reportingBody: string;
    timeframe: string;
    active: boolean;
    createdAt: string;
}

export default function NotifiableConditionsPage() {
    const [conditions, setConditions] = useState<Condition[]>([]);
    const [tests, setTests] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [form, setForm] = useState({
        name: '', organism: '', testIds: [] as string[],
        reportingBody: '', timeframe: '24h', active: true
    });

    const load = async () => {
        setLoading(true);
        try {
            const [cRes, tRes] = await Promise.all([
                fetch('/api/notifiable-conditions'),
                fetch('/api/admin/tests')
            ]);
            const cData = cRes.ok ? await cRes.json() : [];
            const tData = tRes.ok ? await tRes.json() : [];
            setConditions(cData.map((c: any) => ({
                ...c, testIds: Array.isArray(c.testIds) ? c.testIds : JSON.parse(c.testIds || '[]')
            })));
            setTests(tData.filter((t: any) => t.active !== false));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const resetForm = () => {
        setForm({ name: '', organism: '', testIds: [], reportingBody: '', timeframe: '24h', active: true });
        setEditingId(null);
        setShowForm(false);
    };

    const handleSubmit = async () => {
        const url = editingId ? `/api/notifiable-conditions/${editingId}` : '/api/notifiable-conditions';
        const method = editingId ? 'PUT' : 'POST';
        const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) });
        if (res.ok) { resetForm(); load(); }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this notifiable condition?')) return;
        await fetch(`/api/notifiable-conditions/${id}`, { method: 'DELETE' });
        load();
    };

    const startEdit = (c: Condition) => {
        setForm({ name: c.name, organism: c.organism || '', testIds: c.testIds || [], reportingBody: c.reportingBody, timeframe: c.timeframe, active: c.active });
        setEditingId(c.id);
        setShowForm(true);
    };

    const toggleTestId = (id: string) => {
        setForm(f => ({
            ...f,
            testIds: f.testIds.includes(id) ? f.testIds.filter(x => x !== id) : [...f.testIds, id]
        }));
    };

    const TIMEFRAMES = ['1h', '6h', '12h', '24h', '48h', '72h', '1 week'];

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                        <Globe className="w-6 h-6 text-primary-600" />
                        Notifiable Conditions
                    </h1>
                    <p className="text-slate-500 text-sm mt-1">Configure conditions requiring mandatory epidemiology reporting</p>
                </div>
                <button
                    onClick={() => setShowForm(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm font-medium"
                >
                    <Plus className="w-4 h-4" /> Add Condition
                </button>
            </div>

            {showForm && (
                <Card>
                    <h2 className="font-semibold text-slate-800 mb-4">{editingId ? 'Edit Condition' : 'New Notifiable Condition'}</h2>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Condition Name *</label>
                            <input className="input-field w-full" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Typhoid Fever" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Organism</label>
                            <input className="input-field w-full" value={form.organism} onChange={e => setForm(f => ({ ...f, organism: e.target.value }))} placeholder="e.g. Salmonella typhi" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Reporting Body *</label>
                            <input className="input-field w-full" value={form.reportingBody} onChange={e => setForm(f => ({ ...f, reportingBody: e.target.value }))} placeholder="e.g. National Health Authority" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Reporting Timeframe</label>
                            <select className="input-field w-full" value={form.timeframe} onChange={e => setForm(f => ({ ...f, timeframe: e.target.value }))}>
                                {TIMEFRAMES.map(t => <option key={t} value={t}>{t}</option>)}
                            </select>
                        </div>
                        <div className="col-span-2">
                            <label className="block text-sm font-medium text-slate-700 mb-2">Trigger Tests (select any that apply)</label>
                            <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto p-2 border border-slate-200 rounded-lg bg-slate-50">
                                {tests.map(t => (
                                    <button
                                        key={t.id}
                                        type="button"
                                        onClick={() => toggleTestId(t.id)}
                                        className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                                            form.testIds.includes(t.id)
                                                ? 'bg-primary-600 text-white border-primary-600'
                                                : 'bg-white text-slate-700 border-slate-300 hover:border-primary-400'
                                        }`}
                                    >
                                        {t.code} — {t.name}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="flex gap-3 mt-4">
                        <button onClick={handleSubmit} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700">
                            <Save className="w-4 h-4" /> {editingId ? 'Update' : 'Create'}
                        </button>
                        <button onClick={resetForm} className="flex items-center gap-2 px-4 py-2 border border-slate-300 rounded-lg text-sm text-slate-600 hover:bg-slate-50">
                            <X className="w-4 h-4" /> Cancel
                        </button>
                    </div>
                </Card>
            )}

            <Card>
                {loading ? (
                    <div className="text-slate-400 text-center py-8">Loading...</div>
                ) : conditions.length === 0 ? (
                    <div className="text-center py-12 text-slate-400">
                        <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-30" />
                        <p>No notifiable conditions configured</p>
                        <p className="text-sm mt-1">Add conditions that require mandatory reporting</p>
                    </div>
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-200">
                                <th className="text-left py-3 px-4 font-medium text-slate-600">Condition</th>
                                <th className="text-left py-3 px-4 font-medium text-slate-600">Organism</th>
                                <th className="text-left py-3 px-4 font-medium text-slate-600">Reporting Body</th>
                                <th className="text-left py-3 px-4 font-medium text-slate-600">Timeframe</th>
                                <th className="text-left py-3 px-4 font-medium text-slate-600">Trigger Tests</th>
                                <th className="text-left py-3 px-4 font-medium text-slate-600">Status</th>
                                <th className="py-3 px-4" />
                            </tr>
                        </thead>
                        <tbody>
                            {conditions.map(c => (
                                <tr key={c.id} className="border-b border-slate-100 hover:bg-slate-50">
                                    <td className="py-3 px-4 font-medium text-slate-900">{c.name}</td>
                                    <td className="py-3 px-4 text-slate-600 italic">{c.organism || '—'}</td>
                                    <td className="py-3 px-4 text-slate-700">{c.reportingBody}</td>
                                    <td className="py-3 px-4">
                                        <span className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full text-xs font-medium">{c.timeframe}</span>
                                    </td>
                                    <td className="py-3 px-4 text-slate-500 text-xs">
                                        {c.testIds?.length > 0
                                            ? c.testIds.map((tid: string) => tests.find(t => t.id === tid)?.code || tid).join(', ')
                                            : 'Any'
                                        }
                                    </td>
                                    <td className="py-3 px-4">
                                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${c.active ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-500'}`}>
                                            {c.active ? 'Active' : 'Inactive'}
                                        </span>
                                    </td>
                                    <td className="py-3 px-4">
                                        <div className="flex items-center gap-2 justify-end">
                                            <button onClick={() => startEdit(c)} className="p-1.5 text-slate-400 hover:text-primary-600 rounded hover:bg-primary-50 transition-colors">
                                                <Edit2 className="w-4 h-4" />
                                            </button>
                                            <button onClick={() => handleDelete(c.id)} className="p-1.5 text-slate-400 hover:text-red-600 rounded hover:bg-red-50 transition-colors">
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </Card>
        </div>
    );
}
