'use client';

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Table } from '@/components/ui/Table';
import { Plus, Trash2, GitBranch } from 'lucide-react';

interface ReflexRule {
    id: string;
    name: string;
    triggerTestId: string;
    triggerTestCode?: string;
    triggerTestName?: string;
    triggerCondition: string;
    triggerConditionParsed?: { operator: string; value: number };
    addTestId: string;
    addTestCode: string;
    addTestName?: string;
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
    name: '',
    triggerTestId: '',
    operator: '>',
    conditionValue: '',
    addTestId: '',
};

const OPERATORS = ['>', '<', '>=', '<=', '=='];

export default function ReflexRulesPage() {
    const [rules, setRules] = useState<ReflexRule[]>([]);
    const [tests, setTests] = useState<TestDef[]>([]);
    const [form, setForm] = useState(emptyForm);
    const [showForm, setShowForm] = useState(false);
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const loadRules = async () => {
        try {
            const res = await fetch('/api/reflex-rules');
            if (res.ok) setRules(await res.json());
        } catch {
            setMessage('Error: Failed to load reflex rules.');
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

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!form.name || !form.triggerTestId || !form.conditionValue || !form.addTestId) {
            setMessage('Error: All fields are required.');
            return;
        }
        setLoading(true);
        try {
            const res = await fetch('/api/reflex-rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: form.name,
                    triggerTestId: form.triggerTestId,
                    triggerCondition: {
                        operator: form.operator,
                        value: parseFloat(form.conditionValue),
                    },
                    addTestId: form.addTestId,
                }),
            });
            if (res.ok) {
                setMessage('Reflex rule created successfully.');
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

    const handleToggleEnabled = async (rule: ReflexRule) => {
        try {
            const res = await fetch(`/api/reflex-rules/${rule.id}`, {
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

    const handleDelete = async (id: string, name: string) => {
        if (!confirm(`Delete reflex rule "${name}"?`)) return;
        try {
            const res = await fetch(`/api/reflex-rules/${id}`, { method: 'DELETE' });
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

    const formatCondition = (rule: ReflexRule) => {
        const cond = rule.triggerConditionParsed;
        if (!cond) {
            try {
                const parsed = JSON.parse(rule.triggerCondition);
                return `${parsed.operator} ${parsed.value}`;
            } catch {
                return rule.triggerCondition;
            }
        }
        return `${cond.operator} ${cond.value}`;
    };

    const columns = [
        { header: 'Rule Name', accessor: (r: ReflexRule) => <span className="font-semibold">{r.name}</span> },
        {
            header: 'Trigger Test',
            accessor: (r: ReflexRule) => (
                <div>
                    <span className="font-mono text-sm font-semibold">{r.triggerTestCode || r.triggerTestId}</span>
                    {r.triggerTestName && <div className="text-xs text-slate-500">{r.triggerTestName}</div>}
                </div>
            )
        },
        {
            header: 'Condition',
            accessor: (r: ReflexRule) => (
                <span className="font-mono text-sm bg-slate-100 px-2 py-0.5 rounded">
                    {formatCondition(r)}
                </span>
            )
        },
        {
            header: 'Add Test',
            accessor: (r: ReflexRule) => (
                <div>
                    <span className="font-mono text-sm font-semibold">{r.addTestCode}</span>
                    {r.addTestName && <div className="text-xs text-slate-500">{r.addTestName}</div>}
                </div>
            )
        },
        {
            header: 'Enabled',
            accessor: (r: ReflexRule) => (
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
            accessor: (r: ReflexRule) => (
                <button
                    onClick={() => handleDelete(r.id, r.name)}
                    className="text-red-500 hover:text-red-700 p-1 rounded hover:bg-red-50"
                    title="Delete rule"
                >
                    <Trash2 className="w-4 h-4" />
                </button>
            )
        },
    ];

    return (
        <div className="max-w-6xl space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                        <GitBranch className="w-6 h-6 text-indigo-600" /> Reflex Testing Rules
                    </h1>
                    <p className="text-slate-500 mt-1">
                        Automatically order additional tests when a trigger test result meets a defined condition.
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
                <Card title="Add Reflex Rule">
                    <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="md:col-span-2">
                            <label className="label">Rule Name *</label>
                            <input
                                className="input-field"
                                placeholder="e.g. Reflex to Culture if WBC > 11"
                                value={form.name}
                                onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
                                required
                            />
                        </div>

                        <div>
                            <label className="label">Trigger Test *</label>
                            <select
                                className="input-field"
                                value={form.triggerTestId}
                                onChange={e => setForm(prev => ({ ...prev, triggerTestId: e.target.value }))}
                                required
                            >
                                <option value="">Select trigger test...</option>
                                {tests.map(t => (
                                    <option key={t.id} value={t.id}>{t.code} — {t.name}</option>
                                ))}
                            </select>
                        </div>

                        <div className="flex gap-3">
                            <div className="w-32">
                                <label className="label">Operator *</label>
                                <select
                                    className="input-field"
                                    value={form.operator}
                                    onChange={e => setForm(prev => ({ ...prev, operator: e.target.value }))}
                                >
                                    {OPERATORS.map(op => (
                                        <option key={op} value={op}>{op}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex-1">
                                <label className="label">Value *</label>
                                <input
                                    type="number"
                                    step="any"
                                    className="input-field"
                                    placeholder="e.g. 11.0"
                                    value={form.conditionValue}
                                    onChange={e => setForm(prev => ({ ...prev, conditionValue: e.target.value }))}
                                    required
                                />
                            </div>
                        </div>

                        <div>
                            <label className="label">Add Test (Reflex To) *</label>
                            <select
                                className="input-field"
                                value={form.addTestId}
                                onChange={e => setForm(prev => ({ ...prev, addTestId: e.target.value }))}
                                required
                            >
                                <option value="">Select reflex test to add...</option>
                                {tests.map(t => (
                                    <option key={t.id} value={t.id}>{t.code} — {t.name}</option>
                                ))}
                            </select>
                        </div>

                        <div className="md:col-span-2 flex gap-3">
                            <button type="submit" className="btn-primary" disabled={loading}>
                                {loading ? 'Saving...' : 'Create Reflex Rule'}
                            </button>
                            <button type="button" onClick={() => { setShowForm(false); setForm(emptyForm); }} className="btn-secondary">
                                Cancel
                            </button>
                        </div>
                    </form>
                </Card>
            )}

            <Card title={`Reflex Rules (${rules.length})`}>
                <Table
                    data={rules}
                    columns={columns}
                    keyField="id"
                    emptyMessage="No reflex rules defined. Add your first rule above."
                />
            </Card>
        </div>
    );
}
