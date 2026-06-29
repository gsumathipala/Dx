"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Table } from '@/components/ui/Table';
import { Pencil, Trash2, X } from 'lucide-react';

export default function AdminTestsPage() {
    const [message, setMessage] = useState('');
    const [tests, setTests] = useState<any[]>([]);
    const [editingId, setEditingId] = useState<string | null>(null);

    const initialFormState = {
        name: '',
        code: '',
        loincCode: '',
        units: '',
        referenceRange: '',
        panicLow: '',
        panicHigh: '',
        tatHours: 24,
        department: 'Chemistry',
        methodology: '',
        price: ''
    };
    const [newTest, setNewTest] = useState(initialFormState);
    const [currency, setCurrency] = useState('$');
    const [departments, setDepartments] = useState<any[]>([]);

    const loadDeps = async () => {
        try {
            const res = await fetch('/api/admin/departments');
            if (res.ok) setDepartments(await res.json());
        } catch (e) {
            console.error('Failed to load departments');
        }
    };

    const loadSettings = async () => {
        fetch('/api/admin/settings').then(r => r.json()).then(data => {
            if (data.currencySymbol) setCurrency(data.currencySymbol);
        });
    }

    const loadTests = async () => {
        try {
            // Admin page shows all tests including from disabled departments
            const res = await fetch('/api/admin/tests?includeDisabledDepts=true');
            if (res.ok) setTests(await res.json());
        } catch (error) {
            console.error('Failed to load tests:', error);
        }
    };

    useEffect(() => { loadTests(); loadSettings(); loadDeps(); }, []);

    const handleCreateTest = async (e: React.FormEvent) => {
        e.preventDefault();

        // Build structured reference range
        const referenceRange = newTest.referenceRange ? {
            text: newTest.referenceRange,
            min: parseFloat(newTest.referenceRange.split('-')[0]) || null,
            max: parseFloat(newTest.referenceRange.split('-')[1]) || null,
            panicLow: newTest.panicLow ? parseFloat(newTest.panicLow) : null,
            panicHigh: newTest.panicHigh ? parseFloat(newTest.panicHigh) : null,
            unit: newTest.units
        } : null;

        const payload = {
            name: newTest.name,
            code: newTest.code,
            loincCode: newTest.loincCode || null,
            units: newTest.units,
            referenceRange,
            tatHours: newTest.tatHours,
            department: newTest.department,
            methodology: newTest.methodology,
            price: newTest.price
        };

        const method = editingId ? 'PUT' : 'POST';
        const body = editingId ? { ...payload, id: editingId } : payload;

        const res = await fetch('/api/admin/tests', {
            method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(body)
        });

        if (res.ok) {
            setMessage(`Test definition ${editingId ? 'updated' : 'created'} successfully.`);
            setNewTest(initialFormState);
            setEditingId(null);
            loadTests();
        } else {
            const data = await res.json();
            setMessage('Error: ' + data.error);
        }
    };

    const handleEdit = (test: any) => {
        setEditingId(test.id);
        const rangeText = test.referenceRange?.text || (test.referenceRange?.min !== undefined ? `${test.referenceRange.min}-${test.referenceRange.max}` : '');
        setNewTest({
            name: test.name,
            code: test.code,
            loincCode: test.loincCode || '',
            units: test.units || '',
            referenceRange: rangeText,
            panicLow: test.referenceRange?.panicLow || '',
            panicHigh: test.referenceRange?.panicHigh || '',
            tatHours: test.tatHours,
            department: test.department,
            methodology: test.methodology || '',
            price: test.price || ''
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const handleCancelEdit = () => {
        setEditingId(null);
        setNewTest(initialFormState);
    };

    const handleDelete = async (id: string, name: string) => {
        if (!confirm(`Are you sure you want to delete ${name}? This action cannot be undone.`)) return;

        const res = await fetch(`/api/admin/tests?id=${id}`, {
            method: 'DELETE'
        });

        if (res.ok) {
            setMessage('Test deleted successfully.');
            loadTests();
        } else {
            setMessage('Error: Failed to delete test.');
        }
    };

    // Format reference range for display
    const formatRange = (range: any) => {
        if (!range) return '-';
        if (typeof range === 'string') return range;
        return range.text || `${range.min}-${range.max}`;
    };

    const columns = [
        {
            header: 'Test Name', accessor: (t: any) => (
                <div>
                    <div className="font-semibold">{t.name}</div>
                    {t.loincCode && <div className="text-xs text-slate-400">LOINC: {t.loincCode}</div>}
                </div>
            )
        },
        { header: 'Code', accessor: (t: any) => <span className="font-mono text-sm">{t.code || '-'}</span> },
        { header: 'Cost', accessor: (t: any) => <span className="font-bold text-green-700">{currency}{Number(t.price || 0).toFixed(2)}</span> },
        { header: 'Units', accessor: (t: any) => t.units || '-' },
        {
            header: 'Reference Range', accessor: (t: any) => (
                <div>
                    <div>{formatRange(t.referenceRange)}</div>
                    {t.referenceRange?.panicLow && (
                        <div className="text-xs text-red-500">Panic: &lt;{t.referenceRange.panicLow} or &gt;{t.referenceRange.panicHigh}</div>
                    )}
                </div>
            )
        },
        { header: 'TAT', accessor: (t: any) => `${t.tatHours}h` },
        { header: 'Dept', accessor: (t: any) => t.department || '-' },
        {
            header: 'Actions', accessor: (t: any) => (
                <div className="flex gap-2">
                    <button onClick={() => handleEdit(t)} className="text-blue-600 hover:text-blue-800 p-1 rounded hover:bg-blue-50">
                        <Pencil className="w-4 h-4" />
                    </button>
                    <button onClick={() => handleDelete(t.id, t.name)} className="text-red-600 hover:text-red-800 p-1 rounded hover:bg-red-50">
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>
            )
        }
    ];

    return (
        <div className="max-w-6xl space-y-6">
            <h1 className="text-2xl font-bold text-slate-900">Test Definitions</h1>
            <p className="text-slate-500">Configure laboratory tests with LOINC codes, reference ranges, and panic values.</p>

            {message && (
                <div className={`p-4 rounded ${message.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                    {message}
                    <button onClick={() => setMessage('')} className="ml-4 text-sm underline">Dismiss</button>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <Card title={editingId ? `Edit Test: ${newTest.name}` : "Add New Test"} className="lg:col-span-1">
                    <form onSubmit={handleCreateTest} className="space-y-4">
                        <div>
                            <label className="label">Test Name *</label>
                            <input className="input-field" placeholder="e.g. Hemoglobin" required value={newTest.name} onChange={e => setNewTest({ ...newTest, name: e.target.value })} />
                            <div className="mt-2">
                                <label className="label">Price ({currency})</label>
                                <input className="input-field" type="number" step="0.01" placeholder="0.00" value={newTest.price} onChange={e => setNewTest({ ...newTest, price: e.target.value })} />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="label">Code *</label>
                                <input className="input-field" placeholder="HGB" required value={newTest.code} onChange={e => setNewTest({ ...newTest, code: e.target.value.toUpperCase() })} />
                            </div>
                            <div>
                                <label className="label">LOINC Code</label>
                                <input className="input-field" placeholder="718-7" value={newTest.loincCode} onChange={e => setNewTest({ ...newTest, loincCode: e.target.value })} />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="label">Units</label>
                                <input className="input-field" placeholder="g/dL" value={newTest.units} onChange={e => setNewTest({ ...newTest, units: e.target.value })} />
                            </div>
                            <div>
                                <label className="label">Ref. Range</label>
                                <input className="input-field" placeholder="12-16" value={newTest.referenceRange} onChange={e => setNewTest({ ...newTest, referenceRange: e.target.value })} />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="label">Panic Low</label>
                                <input className="input-field" type="number" step="0.1" placeholder="7.0" value={newTest.panicLow} onChange={e => setNewTest({ ...newTest, panicLow: e.target.value })} />
                            </div>
                            <div>
                                <label className="label">Panic High</label>
                                <input className="input-field" type="number" step="0.1" placeholder="20.0" value={newTest.panicHigh} onChange={e => setNewTest({ ...newTest, panicHigh: e.target.value })} />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="label">TAT (Hours)</label>
                                <input className="input-field" type="number" min="1" required value={newTest.tatHours} onChange={e => setNewTest({ ...newTest, tatHours: +e.target.value })} />
                            </div>
                            <div>
                                <div>
                                    <label className="label">Department</label>
                                    <select
                                        className="input-field"
                                        value={newTest.department}
                                        onChange={e => setNewTest({ ...newTest, department: e.target.value })}
                                    >
                                        {departments.length === 0 ? (
                                            <option value="General">General</option>
                                        ) : (
                                            departments.map((d: any) => (
                                                <option key={d.id} value={d.name}>{d.name}</option>
                                            ))
                                        )}
                                    </select>
                                </div>
                            </div>
                        </div>

                        <div>
                            <label className="label">Methodology</label>
                            <input className="input-field" placeholder="e.g. Spectrophotometry" value={newTest.methodology} onChange={e => setNewTest({ ...newTest, methodology: e.target.value })} />
                        </div>

                        <div className="flex gap-2">
                            {editingId && (
                                <button type="button" onClick={handleCancelEdit} className="btn-secondary flex-1">
                                    <X className="w-4 h-4 inline mr-1" /> Cancel
                                </button>
                            )}
                            <button type="submit" className={`btn-primary ${editingId ? 'flex-1' : 'w-full'}`}>
                                {editingId ? 'Update Test' : 'Add Test Definition'}
                            </button>
                        </div>
                    </form>
                </Card>

                <Card title={`Existing Tests (${tests.length})`} className="lg:col-span-2">
                    <div className="overflow-x-auto">
                        <Table data={tests} columns={columns} keyField="id" emptyMessage="No tests defined. Add your first test above." />
                    </div>

                    {tests.length > 0 && (
                        <div className="mt-4 text-xs text-slate-400">
                            💡 LOINC codes enable interoperability with external systems (LIS, EHR, HL7).
                        </div>
                    )}
                </Card>
            </div>
        </div>
    );
}
