'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card } from '@/components/ui/Card';
import { Table } from '@/components/ui/Table';
import { Plus, Search, X, Link, Upload } from 'lucide-react';

interface LoincCode {
    id: string;
    loincCode: string;
    longName: string;
    shortName: string | null;
    component: string | null;
    property: string | null;
    timeAspect: string | null;
    system: string | null;
    scale: string | null;
    method: string | null;
    status: string | null;
}

interface TestDefinition {
    id: string;
    name: string;
    code: string;
}

const BLANK_FORM = {
    loincCode: '', longName: '', shortName: '', component: '',
    property: '', timeAspect: '', system: '', scale: '', method: '',
};

export default function LoincCataloguePage() {
    const [codes, setCodes] = useState<LoincCode[]>([]);
    const [tests, setTests] = useState<TestDefinition[]>([]);
    const [loading, setLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState(BLANK_FORM);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');
    const [linkingCode, setLinkingCode] = useState<LoincCode | null>(null);
    const [linkTestId, setLinkTestId] = useState('');
    const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

    const loadCodes = useCallback(async (q?: string) => {
        setLoading(true);
        try {
            const url = q ? `/api/loinc?q=${encodeURIComponent(q)}` : '/api/loinc';
            const res = await fetch(url);
            if (res.ok) setCodes(await res.json());
        } catch { setMessage('Failed to fetch LOINC codes'); }
        finally { setLoading(false); }
    }, []);

    const loadTests = useCallback(async () => {
        try {
            const res = await fetch('/api/admin/tests');
            if (res.ok) {
                const raw = await res.json();
                setTests(raw.map((t: any) => ({ id: t.id, name: t.name, code: t.code })));
            }
        } catch { /* non-fatal */ }
    }, []);

    useEffect(() => { loadCodes(); loadTests(); }, [loadCodes, loadTests]);

    const handleSearchChange = (value: string) => {
        setSearchQuery(value);
        if (searchTimeout.current) clearTimeout(searchTimeout.current);
        searchTimeout.current = setTimeout(() => { loadCodes(value || undefined); }, 400);
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            const res = await fetch('/api/loinc', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form),
            });
            if (!res.ok) { const err = await res.json(); setMessage(err.error || 'Save failed'); }
            else { setMessage('LOINC code added'); setShowForm(false); setForm(BLANK_FORM); loadCodes(searchQuery || undefined); }
        } finally { setSaving(false); }
    };

    const handleLink = async () => {
        if (!linkingCode || !linkTestId) return;
        // Update the test definition's loinc code via admin tests API (PUT takes id in body)
        const res = await fetch('/api/admin/tests', {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: linkTestId, loincCode: linkingCode.loincCode }),
        });
        if (res.ok) {
            setMessage(`Linked LOINC ${linkingCode.loincCode} to test`);
            setLinkingCode(null);
            setLinkTestId('');
        } else {
            setMessage('Failed to link LOINC code to test');
        }
    };

    const handleImportCsv = () => {
        setMessage('CSV import coming soon — use the manual form to add individual codes for now.');
    };

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">LOINC Code Catalogue</h1>
                    <p className="text-sm text-slate-500 mt-1">Search, browse and manage standardised LOINC codes</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={handleImportCsv}
                        className="flex items-center gap-2 border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                    >
                        <Upload className="w-4 h-4" /> Import CSV
                    </button>
                    <button
                        onClick={() => setShowForm(true)}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    >
                        <Plus className="w-4 h-4" /> Add Code
                    </button>
                </div>
            </div>

            {message && (
                <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-2 rounded-lg text-sm flex justify-between">
                    {message} <button onClick={() => setMessage('')}><X className="w-4 h-4" /></button>
                </div>
            )}

            <Card>
                <div className="p-4 border-b border-slate-100">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search LOINC code, name, or component..."
                            value={searchQuery}
                            onChange={e => handleSearchChange(e.target.value)}
                            className="pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-full max-w-lg"
                        />
                    </div>
                </div>
                <div className="p-4">
                    {loading ? (
                        <p className="text-slate-500 text-sm text-center py-8">Searching...</p>
                    ) : (
                        <Table
                            data={codes}
                            keyField="id"
                            emptyMessage="No LOINC codes found. Try a different search or add codes manually."
                            columns={[
                                {
                                    header: 'LOINC Code',
                                    accessor: c => <span className="font-mono font-semibold text-blue-700">{c.loincCode}</span>
                                },
                                {
                                    header: 'Long Name',
                                    accessor: c => <span className="text-slate-900 max-w-xs truncate block">{c.longName}</span>
                                },
                                { header: 'Component', accessor: c => c.component || '—' },
                                { header: 'Property', accessor: c => c.property || '—' },
                                { header: 'System', accessor: c => c.system || '—' },
                                { header: 'Scale', accessor: c => c.scale || '—' },
                                {
                                    header: 'Status',
                                    accessor: c => (
                                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${c.status === 'Active' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                            {c.status || 'Active'}
                                        </span>
                                    )
                                },
                                {
                                    header: 'Link',
                                    accessor: c => (
                                        <button
                                            onClick={() => { setLinkingCode(c); setLinkTestId(''); }}
                                            className="flex items-center gap-1 text-slate-400 hover:text-blue-600 transition-colors text-xs"
                                            title="Link to test definition"
                                        >
                                            <Link className="w-3.5 h-3.5" /> Link
                                        </button>
                                    )
                                },
                            ]}
                        />
                    )}
                    <p className="text-xs text-slate-400 mt-2 text-right">Showing up to 50 results</p>
                </div>
            </Card>

            {/* Add Code Form */}
            {showForm && (
                <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4">
                    <div className="bg-white w-full max-w-lg rounded-xl shadow-xl max-h-[90vh] overflow-y-auto">
                        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 sticky top-0 bg-white">
                            <h2 className="text-lg font-semibold text-slate-900">Add LOINC Code</h2>
                            <button onClick={() => { setShowForm(false); setForm(BLANK_FORM); }} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
                        </div>
                        <form onSubmit={handleSave} className="p-6 space-y-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">LOINC Code *</label>
                                    <input required value={form.loincCode} onChange={e => setForm(f => ({ ...f, loincCode: e.target.value }))}
                                        placeholder="e.g. 2345-7"
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Short Name</label>
                                    <input value={form.shortName} onChange={e => setForm(f => ({ ...f, shortName: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Long Name *</label>
                                <input required value={form.longName} onChange={e => setForm(f => ({ ...f, longName: e.target.value }))}
                                    placeholder="e.g. Glucose [Moles/volume] in Blood"
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                {[
                                    { label: 'Component', key: 'component', ph: 'e.g. Glucose' },
                                    { label: 'Property', key: 'property', ph: 'e.g. SCnc' },
                                    { label: 'Time Aspect', key: 'timeAspect', ph: 'e.g. Pt' },
                                    { label: 'System', key: 'system', ph: 'e.g. Bld' },
                                    { label: 'Scale', key: 'scale', ph: 'e.g. Qn' },
                                    { label: 'Method', key: 'method', ph: 'e.g. Enzymatic' },
                                ].map(({ label, key, ph }) => (
                                    <div key={key}>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
                                        <input value={(form as any)[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                                            placeholder={ph}
                                            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                    </div>
                                ))}
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button type="submit" disabled={saving}
                                    className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium transition-colors">
                                    {saving ? 'Saving...' : 'Add Code'}
                                </button>
                                <button type="button" onClick={() => { setShowForm(false); setForm(BLANK_FORM); }}
                                    className="flex-1 border border-slate-200 hover:bg-slate-50 text-slate-700 py-2 rounded-lg text-sm font-medium transition-colors">
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Link to Test Modal */}
            {linkingCode && (
                <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4">
                    <div className="bg-white w-full max-w-sm rounded-xl shadow-xl">
                        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                            <h2 className="text-lg font-semibold text-slate-900">Link LOINC to Test</h2>
                            <button onClick={() => setLinkingCode(null)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
                        </div>
                        <div className="p-6 space-y-4">
                            <div className="bg-slate-50 rounded-lg p-3 text-sm">
                                <p className="text-slate-500 text-xs mb-1">LOINC Code</p>
                                <p className="font-mono font-semibold text-blue-700">{linkingCode.loincCode}</p>
                                <p className="text-slate-700 text-xs mt-1">{linkingCode.longName}</p>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Select Test Definition</label>
                                <select value={linkTestId} onChange={e => setLinkTestId(e.target.value)}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                                    <option value="">Choose a test...</option>
                                    {tests.map(t => <option key={t.id} value={t.id}>{t.name} ({t.code})</option>)}
                                </select>
                            </div>
                            <div className="flex gap-3">
                                <button onClick={handleLink} disabled={!linkTestId}
                                    className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium transition-colors">
                                    Link
                                </button>
                                <button onClick={() => setLinkingCode(null)}
                                    className="flex-1 border border-slate-200 hover:bg-slate-50 text-slate-700 py-2 rounded-lg text-sm font-medium transition-colors">
                                    Cancel
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
