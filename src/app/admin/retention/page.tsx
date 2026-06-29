'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Table } from '@/components/ui/Table';
import { Plus, Pencil, Trash2, X, Trash } from 'lucide-react';

interface RetentionPolicy {
    id: string;
    specimenType: string;
    retentionDays: number;
    temperature: string | null;
    disposalMethod: string;
    active: boolean;
    notes: string | null;
    createdAt: string;
}

interface SpecimenRow {
    id: string;
    orderId: string;
    type: string;
    collectionDate: string | null;
    status: string | null;
    accessionNumber?: string;
    patientName?: string;
    dueDate?: string;
    overdue?: boolean;
}

const BLANK_POLICY = {
    specimenType: '',
    retentionDays: 7,
    temperature: '',
    disposalMethod: 'Biohazard Disposal',
    notes: '',
};

export default function RetentionAdminPage() {
    const [activeTab, setActiveTab] = useState<'policies' | 'disposal'>('policies');
    const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
    const [specimens, setSpecimens] = useState<SpecimenRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [form, setForm] = useState(BLANK_POLICY);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [disposing, setDisposing] = useState(false);
    const [batchNotes, setBatchNotes] = useState('');

    const loadPolicies = useCallback(async () => {
        try {
            const res = await fetch('/api/retention');
            if (res.ok) setPolicies(await res.json());
        } catch { setMessage('Failed to load policies'); }
    }, []);

    const loadSpecimens = useCallback(async () => {
        try {
            const res = await fetch('/api/specimens');
            if (!res.ok) return;
            const raw: any[] = await res.json();

            // Enrich with due dates based on retention policies
            const policiesRes = await fetch('/api/retention');
            const pols: RetentionPolicy[] = policiesRes.ok ? await policiesRes.json() : [];
            const policyMap = new Map(pols.map(p => [p.specimenType.toLowerCase(), p]));

            const now = Date.now();
            const enriched: SpecimenRow[] = raw
                .filter(s => s.status !== 'Disposed')
                .map(s => {
                    const policy = policyMap.get((s.type || '').toLowerCase());
                    let dueDate: string | undefined;
                    let overdue = false;
                    if (policy && s.collectionDate) {
                        const due = new Date(s.collectionDate);
                        due.setDate(due.getDate() + policy.retentionDays);
                        dueDate = due.toISOString().slice(0, 10);
                        overdue = due.getTime() <= now;
                    }
                    return {
                        id: s.id,
                        orderId: s.orderId,
                        type: s.type,
                        collectionDate: s.collectionDate,
                        status: s.status,
                        accessionNumber: s.accessionNumber,
                        patientName: s.patientName,
                        dueDate,
                        overdue,
                    };
                })
                .filter(s => s.dueDate) // only show specimens with a known retention policy
                .sort((a, b) => (a.dueDate || '') < (b.dueDate || '') ? -1 : 1);

            setSpecimens(enriched);
        } catch { setMessage('Failed to load specimens'); }
    }, []);

    useEffect(() => {
        const run = async () => {
            setLoading(true);
            await loadPolicies();
            await loadSpecimens();
            setLoading(false);
        };
        run();
    }, [loadPolicies, loadSpecimens]);

    const openAdd = () => { setForm(BLANK_POLICY); setEditingId(null); setShowForm(true); };
    const openEdit = (p: RetentionPolicy) => {
        setForm({
            specimenType: p.specimenType, retentionDays: p.retentionDays,
            temperature: p.temperature || '', disposalMethod: p.disposalMethod, notes: p.notes || '',
        });
        setEditingId(p.id);
        setShowForm(true);
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            const url = editingId ? `/api/retention/${editingId}` : '/api/retention';
            const method = editingId ? 'PUT' : 'POST';
            const res = await fetch(url, {
                method, headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...form, retentionDays: Number(form.retentionDays) }),
            });
            if (!res.ok) { const e = await res.json(); setMessage(e.error || 'Save failed'); }
            else { setMessage(editingId ? 'Policy updated' : 'Policy created'); setShowForm(false); loadPolicies(); }
        } finally { setSaving(false); }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this retention policy?')) return;
        const res = await fetch(`/api/retention/${id}`, { method: 'DELETE' });
        if (res.ok) { setMessage('Policy deleted'); loadPolicies(); }
    };

    const toggleSelect = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const toggleAll = () => {
        if (selectedIds.size === specimens.length) setSelectedIds(new Set());
        else setSelectedIds(new Set(specimens.map(s => s.id)));
    };

    const handleDispose = async () => {
        if (selectedIds.size === 0) { setMessage('Select at least one specimen'); return; }
        if (!confirm(`Dispose ${selectedIds.size} specimen(s)?`)) return;
        setDisposing(true);
        try {
            const res = await fetch('/api/retention/dispose', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ specimenIds: [...selectedIds], notes: batchNotes }),
            });
            if (res.ok) {
                const data = await res.json();
                setMessage(`Disposed ${data.disposed} specimen(s) — Batch: ${data.batchNumber}`);
                setSelectedIds(new Set());
                setBatchNotes('');
                await loadSpecimens();
            } else {
                const e = await res.json();
                setMessage(e.error || 'Disposal failed');
            }
        } finally { setDisposing(false); }
    };

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto">
            <div>
                <h1 className="text-2xl font-bold text-slate-900">Sample Retention & Disposal</h1>
                <p className="text-sm text-slate-500 mt-1">Define retention policies and manage specimen disposal</p>
            </div>

            {message && (
                <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-2 rounded-lg text-sm flex justify-between">
                    {message}
                    <button onClick={() => setMessage('')}><X className="w-4 h-4" /></button>
                </div>
            )}

            {/* Tabs */}
            <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
                {(['policies', 'disposal'] as const).map(t => (
                    <button
                        key={t}
                        onClick={() => setActiveTab(t)}
                        className={`px-4 py-2 rounded-md text-sm font-medium capitalize transition-colors ${activeTab === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
                    >
                        {t === 'policies' ? 'Policies' : 'Disposal Queue'}
                    </button>
                ))}
            </div>

            {activeTab === 'policies' && (
                <Card>
                    <div className="p-4 border-b border-slate-100 flex justify-between items-center">
                        <h2 className="font-semibold text-slate-800">Retention Policies</h2>
                        <button onClick={openAdd} className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
                            <Plus className="w-4 h-4" /> Add Policy
                        </button>
                    </div>
                    <div className="p-4">
                        {loading ? <p className="text-slate-500 text-sm text-center py-8">Loading...</p> : (
                            <Table
                                data={policies}
                                keyField="id"
                                emptyMessage="No retention policies defined."
                                columns={[
                                    { header: 'Specimen Type', accessor: p => <span className="font-medium text-slate-900">{p.specimenType}</span> },
                                    { header: 'Retention (Days)', accessor: p => `${p.retentionDays} days` },
                                    { header: 'Temperature', accessor: p => p.temperature || '—' },
                                    { header: 'Disposal Method', accessor: p => p.disposalMethod },
                                    {
                                        header: 'Status', accessor: p => (
                                            <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${p.active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                                {p.active ? 'Active' : 'Inactive'}
                                            </span>
                                        )
                                    },
                                    {
                                        header: 'Actions', accessor: p => (
                                            <div className="flex gap-2">
                                                <button onClick={() => openEdit(p)} className="text-slate-400 hover:text-blue-600 transition-colors" title="Edit">
                                                    <Pencil className="w-4 h-4" />
                                                </button>
                                                <button onClick={() => handleDelete(p.id)} className="text-slate-400 hover:text-red-500 transition-colors" title="Delete">
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        )
                                    },
                                ]}
                            />
                        )}
                    </div>
                </Card>
            )}

            {activeTab === 'disposal' && (
                <Card>
                    <div className="p-4 border-b border-slate-100">
                        <div className="flex justify-between items-start">
                            <div>
                                <h2 className="font-semibold text-slate-800">Disposal Queue</h2>
                                <p className="text-xs text-slate-500 mt-0.5">Specimens approaching or past their retention date</p>
                            </div>
                            {selectedIds.size > 0 && (
                                <div className="flex items-center gap-3">
                                    <input
                                        type="text"
                                        placeholder="Batch notes..."
                                        value={batchNotes}
                                        onChange={e => setBatchNotes(e.target.value)}
                                        className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 w-48"
                                    />
                                    <button
                                        onClick={handleDispose}
                                        disabled={disposing}
                                        className="flex items-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
                                    >
                                        <Trash className="w-4 h-4" />
                                        {disposing ? 'Processing...' : `Dispose ${selectedIds.size} Selected`}
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="p-4">
                        {loading ? <p className="text-slate-500 text-sm text-center py-8">Loading...</p> : (
                            <div className="overflow-x-auto rounded-lg border border-slate-200">
                                <table className="min-w-full divide-y divide-slate-200">
                                    <thead className="bg-slate-50">
                                        <tr>
                                            <th className="px-4 py-3 text-left">
                                                <input type="checkbox" checked={selectedIds.size === specimens.length && specimens.length > 0} onChange={toggleAll} className="rounded" />
                                            </th>
                                            {['Accession #', 'Specimen Type', 'Collected', 'Due for Disposal', 'Status'].map(h => (
                                                <th key={h} className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-slate-200">
                                        {specimens.length === 0 ? (
                                            <tr><td colSpan={6} className="px-6 py-8 text-center text-slate-500 text-sm">No specimens due for disposal.</td></tr>
                                        ) : specimens.map(s => (
                                            <tr key={s.id} className={s.overdue ? 'bg-red-50' : ''}>
                                                <td className="px-4 py-3">
                                                    <input type="checkbox" checked={selectedIds.has(s.id)} onChange={() => toggleSelect(s.id)} className="rounded" />
                                                </td>
                                                <td className="px-4 py-3 text-sm font-medium text-slate-900">{s.accessionNumber || s.orderId.slice(0, 8)}</td>
                                                <td className="px-4 py-3 text-sm text-slate-700">{s.type}</td>
                                                <td className="px-4 py-3 text-sm text-slate-500">{s.collectionDate ? new Date(s.collectionDate).toLocaleDateString() : '—'}</td>
                                                <td className="px-4 py-3 text-sm">
                                                    <span className={s.overdue ? 'text-red-700 font-semibold' : 'text-amber-700'}>
                                                        {s.dueDate || '—'}
                                                        {s.overdue && ' (Overdue)'}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 text-sm text-slate-500">{s.status || '—'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </Card>
            )}

            {/* Policy Form Modal */}
            {showForm && (
                <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4">
                    <div className="bg-white w-full max-w-md rounded-xl shadow-xl">
                        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                            <h2 className="text-lg font-semibold text-slate-900">{editingId ? 'Edit Policy' : 'Add Retention Policy'}</h2>
                            <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
                        </div>
                        <form onSubmit={handleSave} className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Specimen Type *</label>
                                <input required value={form.specimenType} onChange={e => setForm(f => ({ ...f, specimenType: e.target.value }))}
                                    placeholder="e.g. Whole Blood, Serum, Urine"
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Retention Days *</label>
                                    <input required type="number" min={1} value={form.retentionDays}
                                        onChange={e => setForm(f => ({ ...f, retentionDays: Number(e.target.value) }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Temperature</label>
                                    <input value={form.temperature} onChange={e => setForm(f => ({ ...f, temperature: e.target.value }))}
                                        placeholder="e.g. 4°C, -20°C"
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Disposal Method</label>
                                <input value={form.disposalMethod} onChange={e => setForm(f => ({ ...f, disposalMethod: e.target.value }))}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Notes</label>
                                <textarea rows={2} value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button type="submit" disabled={saving}
                                    className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium transition-colors">
                                    {saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
                                </button>
                                <button type="button" onClick={() => setShowForm(false)}
                                    className="flex-1 border border-slate-200 hover:bg-slate-50 text-slate-700 py-2 rounded-lg text-sm font-medium transition-colors">
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
