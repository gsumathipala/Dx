'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Plus, Pencil, Trash2, X, ChevronDown, ChevronRight } from 'lucide-react';

interface DemoRange {
    id: string;
    testId: string;
    testCode: string;
    ageMin: number | null;
    ageMax: number | null;
    gender: string;
    pregnancy: boolean;
    trimester: number | null;
    lowNormal: number | null;
    highNormal: number | null;
    lowCritical: number | null;
    highCritical: number | null;
    unit: string | null;
    notes: string | null;
    active: boolean;
    createdAt: string;
}

interface TestDefinition {
    id: string;
    name: string;
    code: string;
}

const BLANK_FORM = {
    testId: '', testCode: '', ageMin: '', ageMax: '', gender: 'All',
    pregnancy: false, trimester: '', lowNormal: '', highNormal: '',
    lowCritical: '', highCritical: '', unit: '', notes: '',
};

function ageRangeLabel(min: number | null, max: number | null) {
    if (min == null && max == null) return 'All ages';
    if (min == null) return `≤ ${max}y`;
    if (max == null) return `≥ ${min}y`;
    return `${min}–${max}y`;
}

function RangeRow({ range, onEdit, onDelete }: { range: DemoRange; onEdit: () => void; onDelete: () => void }) {
    return (
        <tr className="hover:bg-slate-50">
            <td className="px-4 py-2 text-sm text-slate-700">{ageRangeLabel(range.ageMin, range.ageMax)}</td>
            <td className="px-4 py-2 text-sm">
                <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${range.gender === 'M' ? 'bg-blue-100 text-blue-700' : range.gender === 'F' ? 'bg-pink-100 text-pink-700' : 'bg-slate-100 text-slate-600'}`}>
                    {range.gender}
                </span>
            </td>
            <td className="px-4 py-2 text-sm text-slate-600">
                {range.pregnancy ? `Yes${range.trimester ? ` (T${range.trimester})` : ''}` : '—'}
            </td>
            <td className="px-4 py-2 text-sm text-slate-900">
                {range.lowNormal != null && range.highNormal != null
                    ? `${range.lowNormal} – ${range.highNormal}`
                    : range.lowNormal != null ? `≥ ${range.lowNormal}`
                        : range.highNormal != null ? `≤ ${range.highNormal}` : '—'}
                {range.unit && <span className="text-slate-400 ml-1 text-xs">{range.unit}</span>}
            </td>
            <td className="px-4 py-2 text-sm text-red-600">
                {range.lowCritical != null && range.highCritical != null
                    ? `< ${range.lowCritical} or > ${range.highCritical}`
                    : '—'}
            </td>
            <td className="px-4 py-2">
                <div className="flex gap-2">
                    <button onClick={onEdit} className="text-slate-400 hover:text-blue-600 transition-colors" title="Edit"><Pencil className="w-3.5 h-3.5" /></button>
                    <button onClick={onDelete} className="text-slate-400 hover:text-red-500 transition-colors" title="Delete"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
            </td>
        </tr>
    );
}

export default function DemographicRangesPage() {
    const [ranges, setRanges] = useState<DemoRange[]>([]);
    const [tests, setTests] = useState<TestDefinition[]>([]);
    const [loading, setLoading] = useState(true);
    const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [form, setForm] = useState(BLANK_FORM);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');
    const [inlineAddTest, setInlineAddTest] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [rRes, tRes] = await Promise.all([
                fetch('/api/demographic-ranges'),
                fetch('/api/admin/tests'),
            ]);
            if (rRes.ok) setRanges(await rRes.json());
            if (tRes.ok) {
                const raw = await tRes.json();
                setTests(raw.map((t: any) => ({ id: t.id, name: t.name, code: t.code })));
            }
        } catch { setMessage('Failed to load data'); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { load(); }, [load]);

    // Group ranges by testCode
    const grouped = tests.reduce((acc, test) => {
        acc[test.code] = { test, ranges: ranges.filter(r => r.testCode === test.code) };
        return acc;
    }, {} as Record<string, { test: TestDefinition; ranges: DemoRange[] }>);

    // Also add groups for any testCodes not in tests list
    ranges.forEach(r => {
        if (!grouped[r.testCode]) {
            grouped[r.testCode] = { test: { id: r.testId, name: r.testCode, code: r.testCode }, ranges: [] };
        }
        if (!grouped[r.testCode].ranges.find(x => x.id === r.id)) {
            grouped[r.testCode].ranges.push(r);
        }
    });

    const toggleCollapse = (code: string) => {
        setCollapsed(prev => {
            const next = new Set(prev);
            if (next.has(code)) next.delete(code); else next.add(code);
            return next;
        });
    };

    const openAdd = (testId?: string, testCode?: string) => {
        const test = tests.find(t => t.id === testId);
        setForm({ ...BLANK_FORM, testId: testId || '', testCode: testCode || test?.code || '' });
        setEditingId(null);
        setInlineAddTest(null);
        setShowForm(true);
    };

    const openEdit = (r: DemoRange) => {
        setForm({
            testId: r.testId, testCode: r.testCode,
            ageMin: r.ageMin != null ? String(r.ageMin) : '',
            ageMax: r.ageMax != null ? String(r.ageMax) : '',
            gender: r.gender, pregnancy: r.pregnancy,
            trimester: r.trimester != null ? String(r.trimester) : '',
            lowNormal: r.lowNormal != null ? String(r.lowNormal) : '',
            highNormal: r.highNormal != null ? String(r.highNormal) : '',
            lowCritical: r.lowCritical != null ? String(r.lowCritical) : '',
            highCritical: r.highCritical != null ? String(r.highCritical) : '',
            unit: r.unit || '', notes: r.notes || '',
        });
        setEditingId(r.id);
        setShowForm(true);
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            const payload = {
                ...form,
                ageMin: form.ageMin !== '' ? Number(form.ageMin) : null,
                ageMax: form.ageMax !== '' ? Number(form.ageMax) : null,
                trimester: form.trimester !== '' ? Number(form.trimester) : null,
                lowNormal: form.lowNormal !== '' ? Number(form.lowNormal) : null,
                highNormal: form.highNormal !== '' ? Number(form.highNormal) : null,
                lowCritical: form.lowCritical !== '' ? Number(form.lowCritical) : null,
                highCritical: form.highCritical !== '' ? Number(form.highCritical) : null,
            };

            // Derive testCode from testId if needed
            if (payload.testId && !payload.testCode) {
                const test = tests.find(t => t.id === payload.testId);
                if (test) payload.testCode = test.code;
            }

            const url = editingId ? `/api/demographic-ranges/${editingId}` : '/api/demographic-ranges';
            const method = editingId ? 'PUT' : 'POST';
            const res = await fetch(url, {
                method, headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!res.ok) { const err = await res.json(); setMessage(err.error || 'Save failed'); }
            else { setMessage(editingId ? 'Range updated' : 'Range created'); setShowForm(false); load(); }
        } finally { setSaving(false); }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this range?')) return;
        const res = await fetch(`/api/demographic-ranges/${id}`, { method: 'DELETE' });
        if (res.ok) { setMessage('Range deleted'); load(); }
    };

    const testGroups = Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b));

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Demographic Reference Ranges</h1>
                    <p className="text-sm text-slate-500 mt-1">Age- and gender-specific normal and critical ranges per test</p>
                </div>
                <button onClick={() => openAdd()}
                    className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                    <Plus className="w-4 h-4" /> Add Range
                </button>
            </div>

            {message && (
                <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-2 rounded-lg text-sm flex justify-between">
                    {message} <button onClick={() => setMessage('')}><X className="w-4 h-4" /></button>
                </div>
            )}

            {loading ? (
                <Card><div className="p-8 text-center text-slate-500 text-sm">Loading...</div></Card>
            ) : testGroups.length === 0 ? (
                <Card><div className="p-8 text-center text-slate-500 text-sm">No tests found. Add test definitions first.</div></Card>
            ) : (
                <div className="space-y-4">
                    {testGroups.map(([code, { test, ranges: testRanges }]) => (
                        <Card key={code}>
                            <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
                                <button
                                    onClick={() => toggleCollapse(code)}
                                    className="flex items-center gap-2 text-left flex-1"
                                >
                                    {collapsed.has(code) ? <ChevronRight className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                                    <span className="font-semibold text-slate-900">{test.name}</span>
                                    <span className="text-xs text-slate-400 font-mono">{code}</span>
                                    <span className="ml-2 text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">{testRanges.length} range(s)</span>
                                </button>
                                <button
                                    onClick={() => openAdd(test.id, test.code)}
                                    className="flex items-center gap-1 text-blue-600 hover:text-blue-800 text-xs font-medium transition-colors"
                                >
                                    <Plus className="w-3.5 h-3.5" /> Add Range
                                </button>
                            </div>

                            {!collapsed.has(code) && (
                                <div className="overflow-x-auto">
                                    <table className="min-w-full divide-y divide-slate-100">
                                        <thead className="bg-slate-50/60">
                                            <tr>
                                                {['Age Range', 'Gender', 'Pregnant', 'Normal Range', 'Critical Range', 'Actions'].map(h => (
                                                    <th key={h} className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase">{h}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100">
                                            {testRanges.length === 0 ? (
                                                <tr>
                                                    <td colSpan={6} className="px-4 py-4 text-center text-slate-400 text-sm italic">
                                                        No ranges defined for this test.
                                                    </td>
                                                </tr>
                                            ) : testRanges.map(r => (
                                                <RangeRow key={r.id} range={r} onEdit={() => openEdit(r)} onDelete={() => handleDelete(r.id)} />
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </Card>
                    ))}
                </div>
            )}

            {/* Add / Edit Form Modal */}
            {showForm && (
                <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4">
                    <div className="bg-white w-full max-w-lg rounded-xl shadow-xl max-h-[90vh] overflow-y-auto">
                        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 sticky top-0 bg-white">
                            <h2 className="text-lg font-semibold text-slate-900">{editingId ? 'Edit Range' : 'Add Demographic Range'}</h2>
                            <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
                        </div>
                        <form onSubmit={handleSave} className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Test *</label>
                                <select required value={form.testId}
                                    onChange={e => {
                                        const t = tests.find(x => x.id === e.target.value);
                                        setForm(f => ({ ...f, testId: e.target.value, testCode: t?.code || '' }));
                                    }}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                                    <option value="">Select test...</option>
                                    {tests.map(t => <option key={t.id} value={t.id}>{t.name} ({t.code})</option>)}
                                </select>
                            </div>
                            <div className="grid grid-cols-3 gap-3">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Min Age (y)</label>
                                    <input type="number" min={0} value={form.ageMin} onChange={e => setForm(f => ({ ...f, ageMin: e.target.value }))}
                                        placeholder="Any"
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Max Age (y)</label>
                                    <input type="number" min={0} value={form.ageMax} onChange={e => setForm(f => ({ ...f, ageMax: e.target.value }))}
                                        placeholder="Any"
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Gender</label>
                                    <select value={form.gender} onChange={e => setForm(f => ({ ...f, gender: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                                        <option value="All">All</option>
                                        <option value="M">Male</option>
                                        <option value="F">Female</option>
                                    </select>
                                </div>
                            </div>
                            <div className="flex items-center gap-4">
                                <label className="flex items-center gap-2 text-sm text-slate-700">
                                    <input type="checkbox" checked={form.pregnancy} onChange={e => setForm(f => ({ ...f, pregnancy: e.target.checked }))}
                                        className="rounded" />
                                    Pregnancy
                                </label>
                                {form.pregnancy && (
                                    <div className="flex items-center gap-2">
                                        <label className="text-sm text-slate-600">Trimester</label>
                                        <select value={form.trimester} onChange={e => setForm(f => ({ ...f, trimester: e.target.value }))}
                                            className="border border-slate-200 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                                            <option value="">Any</option>
                                            <option value="1">1st</option>
                                            <option value="2">2nd</option>
                                            <option value="3">3rd</option>
                                        </select>
                                    </div>
                                )}
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Units</label>
                                <input value={form.unit} onChange={e => setForm(f => ({ ...f, unit: e.target.value }))}
                                    placeholder="e.g. mmol/L"
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Low Normal</label>
                                    <input type="number" step="any" value={form.lowNormal} onChange={e => setForm(f => ({ ...f, lowNormal: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">High Normal</label>
                                    <input type="number" step="any" value={form.highNormal} onChange={e => setForm(f => ({ ...f, highNormal: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Low Critical</label>
                                    <input type="number" step="any" value={form.lowCritical} onChange={e => setForm(f => ({ ...f, lowCritical: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">High Critical</label>
                                    <input type="number" step="any" value={form.highCritical} onChange={e => setForm(f => ({ ...f, highCritical: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
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
