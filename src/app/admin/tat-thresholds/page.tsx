'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Clock, Plus, Trash2, Pencil, Save, X, AlertTriangle } from 'lucide-react';

type TatThreshold = {
    id: string;
    scope: 'test' | 'department' | 'global';
    scopeId: string | null;
    targetHours: number;
    warningHours: number;
    breachHours: number;
    priority: string;
    active: boolean;
    createdAt: string;
};

type ThresholdForm = {
    scope: 'test' | 'department' | 'global';
    scopeId: string;
    targetHours: string;
    warningHours: string;
    breachHours: string;
    priority: 'Routine' | 'STAT';
};

const defaultForm: ThresholdForm = {
    scope: 'global',
    scopeId: '',
    targetHours: '',
    warningHours: '',
    breachHours: '',
    priority: 'Routine',
};

const scopeLabels: Record<string, string> = {
    global: 'Global',
    department: 'Department',
    test: 'Test',
};

export default function TatThresholdsPage() {
    const [thresholds, setThresholds] = useState<TatThreshold[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAddForm, setShowAddForm] = useState(false);
    const [addForm, setAddForm] = useState<ThresholdForm>(defaultForm);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editForm, setEditForm] = useState<ThresholdForm>(defaultForm);
    const [error, setError] = useState('');
    const [saving, setSaving] = useState(false);

    const loadThresholds = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/tat-thresholds');
            if (res.ok) setThresholds(await res.json());
        } catch (err) {
            console.error('Error loading TAT thresholds:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadThresholds();
    }, [loadThresholds]);

    const handleAdd = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError('');
        try {
            const res = await fetch('/api/tat-thresholds', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    scope: addForm.scope,
                    scopeId: addForm.scopeId || undefined,
                    targetHours: parseFloat(addForm.targetHours),
                    warningHours: parseFloat(addForm.warningHours),
                    breachHours: parseFloat(addForm.breachHours),
                    priority: addForm.priority,
                }),
            });
            if (!res.ok) {
                const d = await res.json();
                setError(d.error || 'Failed to add threshold');
                return;
            }
            setAddForm(defaultForm);
            setShowAddForm(false);
            await loadThresholds();
        } catch {
            setError('Network error. Please try again.');
        } finally {
            setSaving(false);
        }
    };

    const handleStartEdit = (t: TatThreshold) => {
        setEditingId(t.id);
        setEditForm({
            scope: t.scope,
            scopeId: t.scopeId || '',
            targetHours: String(t.targetHours),
            warningHours: String(t.warningHours),
            breachHours: String(t.breachHours),
            priority: (t.priority as 'Routine' | 'STAT') || 'Routine',
        });
        setError('');
    };

    const handleSaveEdit = async (id: string) => {
        setSaving(true);
        setError('');
        try {
            const res = await fetch(`/api/tat-thresholds/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    scope: editForm.scope,
                    scopeId: editForm.scopeId || null,
                    targetHours: parseFloat(editForm.targetHours),
                    warningHours: parseFloat(editForm.warningHours),
                    breachHours: parseFloat(editForm.breachHours),
                    priority: editForm.priority,
                }),
            });
            if (!res.ok) {
                const d = await res.json();
                setError(d.error || 'Failed to save');
                return;
            }
            setEditingId(null);
            await loadThresholds();
        } catch {
            setError('Network error. Please try again.');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this TAT threshold?')) return;
        try {
            const res = await fetch(`/api/tat-thresholds/${id}`, { method: 'DELETE' });
            if (!res.ok) {
                const d = await res.json();
                setError(d.error || 'Failed to delete');
                return;
            }
            await loadThresholds();
        } catch {
            setError('Network error. Please try again.');
        }
    };

    return (
        <div className="p-6 space-y-6 max-w-6xl mx-auto">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-amber-50 rounded-lg">
                        <Clock className="h-6 w-6 text-amber-600" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">TAT Threshold Configuration</h1>
                        <p className="text-sm text-slate-500">Configure turnaround time thresholds for monitoring</p>
                    </div>
                </div>
                <button
                    onClick={() => { setShowAddForm(true); setError(''); }}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
                >
                    <Plus className="h-4 w-4" /> Add Threshold
                </button>
            </div>

            {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                    <AlertTriangle className="h-4 w-4 flex-shrink-0" /> {error}
                </div>
            )}

            {/* Add Form */}
            {showAddForm && (
                <Card title="Add New Threshold">
                    <form onSubmit={handleAdd} className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 items-end">
                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Scope *</label>
                            <select
                                value={addForm.scope}
                                onChange={e => setAddForm(f => ({ ...f, scope: e.target.value as ThresholdForm['scope'] }))}
                                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                                required
                            >
                                <option value="global">Global</option>
                                <option value="department">Department</option>
                                <option value="test">Test</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Scope ID {addForm.scope !== 'global' ? '*' : ''}</label>
                            <input
                                type="text"
                                value={addForm.scopeId}
                                onChange={e => setAddForm(f => ({ ...f, scopeId: e.target.value }))}
                                placeholder={addForm.scope === 'department' ? 'Dept code' : addForm.scope === 'test' ? 'Test code' : 'N/A'}
                                disabled={addForm.scope === 'global'}
                                required={addForm.scope !== 'global'}
                                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white disabled:bg-slate-100"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Target (hrs) *</label>
                            <input
                                type="number"
                                value={addForm.targetHours}
                                onChange={e => setAddForm(f => ({ ...f, targetHours: e.target.value }))}
                                placeholder="e.g. 24"
                                step="0.5"
                                min="0"
                                required
                                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Warning (hrs) *</label>
                            <input
                                type="number"
                                value={addForm.warningHours}
                                onChange={e => setAddForm(f => ({ ...f, warningHours: e.target.value }))}
                                placeholder="e.g. 20"
                                step="0.5"
                                min="0"
                                required
                                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Breach (hrs) *</label>
                            <input
                                type="number"
                                value={addForm.breachHours}
                                onChange={e => setAddForm(f => ({ ...f, breachHours: e.target.value }))}
                                placeholder="e.g. 28"
                                step="0.5"
                                min="0"
                                required
                                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Priority</label>
                            <select
                                value={addForm.priority}
                                onChange={e => setAddForm(f => ({ ...f, priority: e.target.value as 'Routine' | 'STAT' }))}
                                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                            >
                                <option value="Routine">Routine</option>
                                <option value="STAT">STAT</option>
                            </select>
                        </div>
                        <div className="col-span-full flex gap-2">
                            <button
                                type="submit"
                                disabled={saving}
                                className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
                            >
                                {saving ? 'Saving...' : 'Add Threshold'}
                            </button>
                            <button
                                type="button"
                                onClick={() => setShowAddForm(false)}
                                className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-md text-sm font-medium hover:bg-slate-50 transition-colors"
                            >
                                Cancel
                            </button>
                        </div>
                    </form>
                </Card>
            )}

            {/* Thresholds Table */}
            <Card title="Configured Thresholds">
                {loading ? (
                    <div className="flex items-center justify-center py-12 text-slate-400">
                        <Clock className="h-5 w-5 animate-spin mr-2" /> Loading...
                    </div>
                ) : thresholds.length === 0 ? (
                    <div className="text-center py-12 text-slate-400 text-sm">
                        No TAT thresholds configured. Click &ldquo;Add Threshold&rdquo; to create one.
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200">
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Scope</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Scope ID</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Target (hrs)</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Warning (hrs)</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Breach (hrs)</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Priority</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {thresholds.map(t => (
                                    <tr key={t.id} className="hover:bg-slate-50">
                                        {editingId === t.id ? (
                                            <>
                                                <td className="py-2 px-3">
                                                    <select
                                                        value={editForm.scope}
                                                        onChange={e => setEditForm(f => ({ ...f, scope: e.target.value as ThresholdForm['scope'] }))}
                                                        className="border border-slate-300 rounded px-2 py-1 text-xs w-28"
                                                    >
                                                        <option value="global">Global</option>
                                                        <option value="department">Department</option>
                                                        <option value="test">Test</option>
                                                    </select>
                                                </td>
                                                <td className="py-2 px-3">
                                                    <input
                                                        type="text"
                                                        value={editForm.scopeId}
                                                        onChange={e => setEditForm(f => ({ ...f, scopeId: e.target.value }))}
                                                        disabled={editForm.scope === 'global'}
                                                        className="border border-slate-300 rounded px-2 py-1 text-xs w-24 disabled:bg-slate-100"
                                                        placeholder="ID"
                                                    />
                                                </td>
                                                <td className="py-2 px-3">
                                                    <input type="number" value={editForm.targetHours} onChange={e => setEditForm(f => ({ ...f, targetHours: e.target.value }))} className="border border-slate-300 rounded px-2 py-1 text-xs w-16" step="0.5" min="0" />
                                                </td>
                                                <td className="py-2 px-3">
                                                    <input type="number" value={editForm.warningHours} onChange={e => setEditForm(f => ({ ...f, warningHours: e.target.value }))} className="border border-slate-300 rounded px-2 py-1 text-xs w-16" step="0.5" min="0" />
                                                </td>
                                                <td className="py-2 px-3">
                                                    <input type="number" value={editForm.breachHours} onChange={e => setEditForm(f => ({ ...f, breachHours: e.target.value }))} className="border border-slate-300 rounded px-2 py-1 text-xs w-16" step="0.5" min="0" />
                                                </td>
                                                <td className="py-2 px-3">
                                                    <select value={editForm.priority} onChange={e => setEditForm(f => ({ ...f, priority: e.target.value as 'Routine' | 'STAT' }))} className="border border-slate-300 rounded px-2 py-1 text-xs">
                                                        <option value="Routine">Routine</option>
                                                        <option value="STAT">STAT</option>
                                                    </select>
                                                </td>
                                                <td className="py-2 px-3 flex items-center gap-1">
                                                    <button onClick={() => handleSaveEdit(t.id)} disabled={saving} className="p-1 text-green-600 hover:bg-green-50 rounded" title="Save">
                                                        <Save className="h-4 w-4" />
                                                    </button>
                                                    <button onClick={() => setEditingId(null)} className="p-1 text-slate-500 hover:bg-slate-100 rounded" title="Cancel">
                                                        <X className="h-4 w-4" />
                                                    </button>
                                                </td>
                                            </>
                                        ) : (
                                            <>
                                                <td className="py-2 px-3">
                                                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${t.scope === 'global' ? 'bg-purple-100 text-purple-700' : t.scope === 'department' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}`}>
                                                        {scopeLabels[t.scope]}
                                                    </span>
                                                </td>
                                                <td className="py-2 px-3 text-slate-600">{t.scopeId || <span className="text-slate-400 italic">—</span>}</td>
                                                <td className="py-2 px-3 font-medium text-slate-800">{t.targetHours}h</td>
                                                <td className="py-2 px-3 text-amber-600 font-medium">{t.warningHours}h</td>
                                                <td className="py-2 px-3 text-red-600 font-medium">{t.breachHours}h</td>
                                                <td className="py-2 px-3">
                                                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${t.priority === 'STAT' ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-600'}`}>
                                                        {t.priority}
                                                    </span>
                                                </td>
                                                <td className="py-2 px-3">
                                                    <div className="flex items-center gap-1">
                                                        <button onClick={() => handleStartEdit(t)} className="p-1 text-blue-500 hover:bg-blue-50 rounded" title="Edit">
                                                            <Pencil className="h-4 w-4" />
                                                        </button>
                                                        <button onClick={() => handleDelete(t.id)} className="p-1 text-red-500 hover:bg-red-50 rounded" title="Delete">
                                                            <Trash2 className="h-4 w-4" />
                                                        </button>
                                                    </div>
                                                </td>
                                            </>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </Card>
        </div>
    );
}
