'use client';

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Table } from '@/components/ui/Table';
import { Plus, Trash2, Activity } from 'lucide-react';

interface DeltaRule {
    id: string;
    testId: string;
    testCode: string;
    deltaType: 'percent' | 'absolute';
    threshold: number;
    direction: 'any' | 'increase' | 'decrease';
    enabled: boolean;
    createdAt: string;
    createdBy?: string;
}

interface TestDef {
    id: string;
    code: string;
    name: string;
}

const emptyForm = {
    testId: '',
    testCode: '',
    deltaType: 'percent' as 'percent' | 'absolute',
    threshold: '',
    direction: 'any' as 'any' | 'increase' | 'decrease',
};

export default function DeltaChecksPage() {
    const [rules, setRules] = useState<DeltaRule[]>([]);
    const [tests, setTests] = useState<TestDef[]>([]);
    const [form, setForm] = useState(emptyForm);
    const [showForm, setShowForm] = useState(false);
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const loadRules = async () => {
        try {
            const res = await fetch('/api/delta-checks/rules');
            if (res.ok) setRules(await res.json());
        } catch {
            setMessage('Error: Failed to load rules.');
        }
    };

    const loadTests = async () => {
        try {
            const res = await fetch('/api/admin/tests');
            if (res.ok) setTests(await res.json());
        } catch { /* silently fail */ }
    };

    useEffect(() => {
        loadRules();
        loadTests();
    }, []);

    const handleTestSelect = (testId: string) => {
        const test = tests.find(t => t.id === testId);
        setForm(prev => ({ ...prev, testId, testCode: test?.code || '' }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!form.testId || !form.threshold) {
            setMessage('Error: Test and threshold are required.');
            return;
        }
        setLoading(true);
        try {
            const res = await fetch('/api/delta-checks/rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    testId: form.testId,
                    testCode: form.testCode,
                    deltaType: form.deltaType,
                    threshold: parseFloat(form.threshold),
                    direction: form.direction,
                }),
            });
            if (res.ok) {
                setMessage('Rule created successfully.');
                setForm(emptyForm);
                setShowForm(false);
                loadRules();
            } else {
                const data = await res.json();
                setMessage('Error: ' + (data.error || 'Failed to create rule.'));
            }
        } catch {
            setMessage('Error: Network error.');
        } finally {
            setLoading(false);
        }
    };

    const handleToggleEnabled = async (rule: DeltaRule) => {
        try {
            const res = await fetch(`/api/delta-checks/rules/${rule.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !rule.enabled }),
            });
            if (res.ok) {
                setRules(prev => prev.map(r => r.id === rule.id ? { ...r, enabled: !r.enabled } : r));
            }
        } catch {
            setMessage('Error: Failed to update rule.');
        }
    };

    const handleDelete = async (id: string, testCode: string) => {
        if (!confirm(`Delete delta check rule for ${testCode}?`)) return;
        try {
            const res = await fetch(`/api/delta-checks/rules/${id}`, { method: 'DELETE' });
            if (res.ok) {
                setMessage('Rule deleted.');
                loadRules();
            } else {
                setMessage('Error: Failed to delete rule.');
            }
        } catch {
            setMessage('Error: Network error.');
        }
    };

    const columns = [
        { header: 'Test Code', accessor: (r: DeltaRule) => <span className="font-mono font-semibold">{r.testCode}</span> },
        {
            header: 'Type',
            accessor: (r: DeltaRule) => (
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${r.deltaType === 'percent' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                    {r.deltaType === 'percent' ? 'Percent %' : 'Absolute'}
                </span>
            )
        },
        {
            header: 'Threshold',
            accessor: (r: DeltaRule) => (
                <span className="font-semibold">
                    {r.threshold}{r.deltaType === 'percent' ? '%' : ''}
                </span>
            )
        },
        {
            header: 'Direction',
            accessor: (r: DeltaRule) => (
                <span className="capitalize text-slate-600">{r.direction}</span>
            )
        },
        {
            header: 'Enabled',
            accessor: (r: DeltaRule) => (
                <button
                    onClick={() => handleToggleEnabled(r)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${r.enabled ? 'bg-green-500' : 'bg-slate-300'}`}
                    title={r.enabled ? 'Disable' : 'Enable'}
                >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${r.enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
            )
        },
        {
            header: 'Actions',
            accessor: (r: DeltaRule) => (
                <button
                    onClick={() => handleDelete(r.id, r.testCode)}
                    className="text-red-500 hover:text-red-700 p-1 rounded hover:bg-red-50"
                    title="Delete rule"
                >
                    <Trash2 className="w-4 h-4" />
                </button>
            )
        },
    ];

    return (
        <div className="max-w-5xl space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                        <Activity className="w-6 h-6 text-blue-600" /> Delta Check Rules
                    </h1>
                    <p className="text-slate-500 mt-1">
                        Flag results where a value has changed significantly from the patient's previous result.
                    </p>
                </div>
                <button
                    onClick={() => setShowForm(prev => !prev)}
                    className="btn-primary flex items-center gap-2"
                >
                    <Plus className="w-4 h-4" />
                    {showForm ? 'Cancel' : 'Add Rule'}
                </button>
            </div>

            {message && (
                <div className={`p-3 rounded text-sm ${message.startsWith('Error') ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
                    {message}
                    <button onClick={() => setMessage('')} className="ml-3 underline text-xs">Dismiss</button>
                </div>
            )}

            {showForm && (
                <Card title="Add Delta Check Rule">
                    <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="lg:col-span-2">
                            <label className="label">Test *</label>
                            <select
                                className="input-field"
                                value={form.testId}
                                onChange={e => handleTestSelect(e.target.value)}
                                required
                            >
                                <option value="">Select a test...</option>
                                {tests.map(t => (
                                    <option key={t.id} value={t.id}>{t.code} — {t.name}</option>
                                ))}
                            </select>
                        </div>

                        <div>
                            <label className="label">Delta Type *</label>
                            <select
                                className="input-field"
                                value={form.deltaType}
                                onChange={e => setForm(prev => ({ ...prev, deltaType: e.target.value as 'percent' | 'absolute' }))}
                            >
                                <option value="percent">Percent (%)</option>
                                <option value="absolute">Absolute</option>
                            </select>
                        </div>

                        <div>
                            <label className="label">Threshold *</label>
                            <input
                                type="number"
                                step="0.1"
                                min="0"
                                className="input-field"
                                placeholder={form.deltaType === 'percent' ? 'e.g. 20' : 'e.g. 2.5'}
                                value={form.threshold}
                                onChange={e => setForm(prev => ({ ...prev, threshold: e.target.value }))}
                                required
                            />
                        </div>

                        <div>
                            <label className="label">Direction</label>
                            <select
                                className="input-field"
                                value={form.direction}
                                onChange={e => setForm(prev => ({ ...prev, direction: e.target.value as 'any' | 'increase' | 'decrease' }))}
                            >
                                <option value="any">Any</option>
                                <option value="increase">Increase only</option>
                                <option value="decrease">Decrease only</option>
                            </select>
                        </div>

                        <div className="lg:col-span-3 flex items-end">
                            <button
                                type="submit"
                                className="btn-primary"
                                disabled={loading}
                            >
                                {loading ? 'Saving...' : 'Create Rule'}
                            </button>
                        </div>
                    </form>
                </Card>
            )}

            <Card title={`Rules (${rules.length})`}>
                <Table
                    data={rules}
                    columns={columns}
                    keyField="id"
                    emptyMessage="No delta check rules defined. Add your first rule above."
                />
            </Card>
        </div>
    );
}
