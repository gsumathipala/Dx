'use client';

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Plus, Trash2, ToggleLeft, ToggleRight, Mail, Printer, Phone, Globe } from 'lucide-react';

interface DistributionRule {
    id: string;
    requesterId: string | null;
    requesterName: string;
    testId: string | null;
    method: 'email' | 'print' | 'fax' | 'portal';
    destination: string | null;
    autoRelease: boolean;
    active: boolean;
    createdAt: string;
}

interface Requester {
    id: string;
    name: string;
    type: string;
}

interface TestDef {
    id: string;
    code: string;
    name: string;
}

const METHOD_ICONS: Record<string, React.ElementType> = {
    email: Mail,
    print: Printer,
    fax: Phone,
    portal: Globe,
};

const METHOD_COLORS: Record<string, string> = {
    email: 'bg-blue-100 text-blue-700',
    print: 'bg-slate-100 text-slate-700',
    fax: 'bg-amber-100 text-amber-700',
    portal: 'bg-emerald-100 text-emerald-700',
};

const emptyForm = {
    requesterId: '',
    testId: '',
    method: 'email' as 'email' | 'print' | 'fax' | 'portal',
    destination: '',
    autoRelease: false,
};

export default function DistributionRulesPage() {
    const [rules, setRules] = useState<DistributionRule[]>([]);
    const [requesters, setRequesters] = useState<Requester[]>([]);
    const [testDefs, setTestDefs] = useState<TestDef[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState(emptyForm);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const loadRules = () =>
        fetch('/api/distribution-rules')
            .then((r) => r.json())
            .then((data) => setRules(Array.isArray(data) ? data : []));

    useEffect(() => {
        Promise.all([
            loadRules(),
            fetch('/api/requesters').then((r) => r.json()).then((d) => setRequesters(Array.isArray(d) ? d : (d.requesters ?? []))),
            fetch('/api/admin/tests').then((r) => r.json()).then((d) => setTestDefs(Array.isArray(d) ? d : (d.tests ?? []))),
        ]).finally(() => setLoading(false));
    }, []);

    const handleAdd = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (!form.method) { setError('Method is required'); return; }
        setSaving(true);
        try {
            const res = await fetch('/api/distribution-rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    requesterId: form.requesterId || null,
                    testId: form.testId || null,
                    method: form.method,
                    destination: form.destination || null,
                    autoRelease: form.autoRelease,
                }),
            });
            if (!res.ok) {
                const json = await res.json();
                setError(json.error ?? 'Failed to create rule');
                return;
            }
            await loadRules();
            setForm(emptyForm);
            setShowForm(false);
        } finally {
            setSaving(false);
        }
    };

    const handleToggle = async (rule: DistributionRule, field: 'active' | 'autoRelease') => {
        await fetch(`/api/distribution-rules/${rule.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [field]: !rule[field] }),
        });
        await loadRules();
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this distribution rule?')) return;
        await fetch(`/api/distribution-rules/${id}`, { method: 'DELETE' });
        setRules((prev) => prev.filter((r) => r.id !== id));
    };

    return (
        <div className="min-h-screen bg-slate-50 p-6">
            <div className="max-w-6xl mx-auto space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">Distribution Rules</h1>
                        <p className="text-slate-500 text-sm mt-1">Configure result delivery rules for requesters</p>
                    </div>
                    <button
                        onClick={() => setShowForm(!showForm)}
                        className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
                    >
                        <Plus size={16} />
                        Add Rule
                    </button>
                </div>

                {/* Add Rule Form */}
                {showForm && (
                    <Card title="New Distribution Rule">
                        <form onSubmit={handleAdd} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            <div>
                                <label className="block text-xs font-medium text-slate-600 mb-1">Requester</label>
                                <select
                                    value={form.requesterId}
                                    onChange={(e) => setForm((f) => ({ ...f, requesterId: e.target.value }))}
                                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                                >
                                    <option value="">All Requesters</option>
                                    {requesters.map((r) => (
                                        <option key={r.id} value={r.id}>{r.name} ({r.type})</option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-slate-600 mb-1">Test Filter</label>
                                <select
                                    value={form.testId}
                                    onChange={(e) => setForm((f) => ({ ...f, testId: e.target.value }))}
                                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                                >
                                    <option value="">All Tests</option>
                                    {testDefs.map((t) => (
                                        <option key={t.id} value={t.id}>{t.code} – {t.name}</option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-slate-600 mb-1">Method *</label>
                                <select
                                    value={form.method}
                                    onChange={(e) => setForm((f) => ({ ...f, method: e.target.value as typeof form.method }))}
                                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                                    required
                                >
                                    <option value="email">Email</option>
                                    <option value="print">Print</option>
                                    <option value="fax">Fax</option>
                                    <option value="portal">Portal</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-slate-600 mb-1">Destination</label>
                                <input
                                    type="text"
                                    value={form.destination}
                                    onChange={(e) => setForm((f) => ({ ...f, destination: e.target.value }))}
                                    placeholder={form.method === 'email' ? 'email@example.com' : form.method === 'fax' ? 'fax number' : 'destination'}
                                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                                />
                            </div>

                            <div className="flex items-center gap-3 pt-5">
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={form.autoRelease}
                                        onChange={(e) => setForm((f) => ({ ...f, autoRelease: e.target.checked }))}
                                        className="w-4 h-4 accent-blue-600"
                                    />
                                    <span className="text-sm text-slate-700">Auto-Release</span>
                                </label>
                            </div>

                            <div className="flex items-end gap-2">
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
                                >
                                    {saving ? 'Saving...' : 'Save Rule'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => { setShowForm(false); setForm(emptyForm); setError(''); }}
                                    className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 text-sm"
                                >
                                    Cancel
                                </button>
                            </div>

                            {error && (
                                <div className="col-span-full text-red-600 text-sm bg-red-50 px-3 py-2 rounded-lg">
                                    {error}
                                </div>
                            )}
                        </form>
                    </Card>
                )}

                {/* Rules Table */}
                <Card title={`Rules (${rules.length})`}>
                    {loading ? (
                        <div className="text-center py-10 text-slate-400 text-sm">Loading...</div>
                    ) : rules.length === 0 ? (
                        <div className="text-center py-10 text-slate-400 text-sm">
                            No distribution rules configured. Click "Add Rule" to create one.
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-slate-100">
                                        <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Requester</th>
                                        <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Test Filter</th>
                                        <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Method</th>
                                        <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Destination</th>
                                        <th className="text-center py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Auto-Release</th>
                                        <th className="text-center py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Active</th>
                                        <th className="py-3 px-4"></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rules.map((rule) => {
                                        const MethodIcon = METHOD_ICONS[rule.method] ?? Globe;
                                        const testDef = testDefs.find((t) => t.id === rule.testId);
                                        return (
                                            <tr key={rule.id} className="border-b border-slate-50 hover:bg-slate-50">
                                                <td className="py-3 px-4 font-medium text-slate-800">{rule.requesterName}</td>
                                                <td className="py-3 px-4 text-slate-600">
                                                    {testDef ? (
                                                        <span className="font-mono text-xs bg-slate-100 px-2 py-0.5 rounded">{testDef.code}</span>
                                                    ) : (
                                                        <span className="text-slate-400 text-xs">All Tests</span>
                                                    )}
                                                </td>
                                                <td className="py-3 px-4">
                                                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${METHOD_COLORS[rule.method]}`}>
                                                        <MethodIcon size={12} />
                                                        {rule.method.charAt(0).toUpperCase() + rule.method.slice(1)}
                                                    </span>
                                                </td>
                                                <td className="py-3 px-4 text-slate-600 text-xs">{rule.destination ?? '—'}</td>
                                                <td className="py-3 px-4 text-center">
                                                    <button onClick={() => handleToggle(rule, 'autoRelease')} className="text-slate-400 hover:text-slate-700">
                                                        {rule.autoRelease ? (
                                                            <ToggleRight size={22} className="text-blue-500" />
                                                        ) : (
                                                            <ToggleLeft size={22} />
                                                        )}
                                                    </button>
                                                </td>
                                                <td className="py-3 px-4 text-center">
                                                    <button onClick={() => handleToggle(rule, 'active')} className="text-slate-400 hover:text-slate-700">
                                                        {rule.active ? (
                                                            <ToggleRight size={22} className="text-emerald-500" />
                                                        ) : (
                                                            <ToggleLeft size={22} />
                                                        )}
                                                    </button>
                                                </td>
                                                <td className="py-3 px-4">
                                                    <button
                                                        onClick={() => handleDelete(rule.id)}
                                                        className="text-slate-300 hover:text-red-500 transition-colors"
                                                    >
                                                        <Trash2 size={15} />
                                                    </button>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </Card>
            </div>
        </div>
    );
}
