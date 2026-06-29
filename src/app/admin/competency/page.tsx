'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Table } from '@/components/ui/Table';
import { Plus, Pencil, Trash2, X, Printer } from 'lucide-react';

type CompetencyStatus = 'Active' | 'Expired' | 'Suspended';

interface CompetencyRecord {
    id: string;
    userId: string;
    testId: string | null;
    category: string | null;
    competencyDate: string;
    expiryDate: string;
    assessedBy: string;
    status: CompetencyStatus;
    notes: string | null;
    createdAt: string;
    userName?: string;
    userUsername?: string;
    userDepartment?: string;
}

interface UserOption {
    id: string;
    name: string;
    username: string;
    department?: string;
}

interface TestOption {
    id: string;
    name: string;
    code: string;
}

const STATUS_COLORS: Record<CompetencyStatus, string> = {
    Active: 'bg-green-100 text-green-700',
    Expired: 'bg-red-100 text-red-700',
    Suspended: 'bg-amber-100 text-amber-700',
};

const BLANK_FORM = {
    userId: '', testId: '', category: '', competencyDate: '', expiryDate: '', notes: '',
};

export default function CompetencyAdminPage() {
    const [records, setRecords] = useState<CompetencyRecord[]>([]);
    const [users, setUsers] = useState<UserOption[]>([]);
    const [tests, setTests] = useState<TestOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [filterUser, setFilterUser] = useState('');
    const [filterDept, setFilterDept] = useState('');
    const [filterStatus, setFilterStatus] = useState('');
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editStatus, setEditStatus] = useState<CompetencyStatus | null>(null);
    const [form, setForm] = useState(BLANK_FORM);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');

    const loadRecords = useCallback(async () => {
        try {
            const res = await fetch('/api/competency');
            if (res.ok) setRecords(await res.json());
        } catch { setMessage('Failed to load competency records'); }
    }, []);

    useEffect(() => {
        const run = async () => {
            setLoading(true);
            await loadRecords();
            try {
                const [uRes, tRes] = await Promise.all([
                    fetch('/api/users/list'),
                    fetch('/api/admin/tests'),
                ]);
                if (uRes.ok) {
                    const raw = await uRes.json();
                    setUsers(raw.map((u: any) => ({ id: u.id || u.username, name: u.name, username: u.username, department: u.department })));
                }
                if (tRes.ok) {
                    const raw = await tRes.json();
                    setTests(raw.map((t: any) => ({ id: t.id, name: t.name, code: t.code })));
                }
            } catch { /* non-fatal */ }
            setLoading(false);
        };
        run();
    }, [loadRecords]);

    const departments = [...new Set(users.map(u => u.department).filter(Boolean))] as string[];

    const filtered = records.filter(r => {
        if (filterUser && r.userId !== filterUser) return false;
        if (filterDept && r.userDepartment !== filterDept) return false;
        if (filterStatus && r.status !== filterStatus) return false;
        return true;
    });

    const openAdd = () => {
        setForm(BLANK_FORM);
        setEditingId(null);
        setEditStatus(null);
        setShowForm(true);
    };

    const openEdit = (r: CompetencyRecord) => {
        setForm({ userId: r.userId, testId: r.testId || '', category: r.category || '', competencyDate: r.competencyDate, expiryDate: r.expiryDate, notes: r.notes || '' });
        setEditingId(r.id);
        setEditStatus(r.status);
        setShowForm(true);
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            const url = editingId ? `/api/competency/${editingId}` : '/api/competency';
            const method = editingId ? 'PUT' : 'POST';
            const payload = editingId ? { ...form, status: editStatus } : form;
            const res = await fetch(url, {
                method, headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!res.ok) { const e = await res.json(); setMessage(e.error || 'Save failed'); }
            else { setMessage(editingId ? 'Record updated' : 'Record created'); setShowForm(false); loadRecords(); }
        } finally { setSaving(false); }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this competency record?')) return;
        const res = await fetch(`/api/competency/${id}`, { method: 'DELETE' });
        if (res.ok) { setMessage('Record deleted'); loadRecords(); }
    };

    const isExpiringSoon = (expiryDate: string) => {
        const days = (new Date(expiryDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24);
        return days >= 0 && days <= 30;
    };

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">User Competency Matrix</h1>
                    <p className="text-sm text-slate-500 mt-1">Track staff competencies, assessments and expiry dates</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => window.print()}
                        className="flex items-center gap-2 border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                    >
                        <Printer className="w-4 h-4" /> Export Matrix
                    </button>
                    <button
                        onClick={openAdd}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    >
                        <Plus className="w-4 h-4" /> Add Record
                    </button>
                </div>
            </div>

            {message && (
                <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-2 rounded-lg text-sm flex justify-between">
                    {message} <button onClick={() => setMessage('')}><X className="w-4 h-4" /></button>
                </div>
            )}

            {/* Filters */}
            <Card>
                <div className="p-4 flex flex-wrap gap-3 items-center">
                    <select value={filterUser} onChange={e => setFilterUser(e.target.value)}
                        className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="">All Users</option>
                        {users.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
                    </select>
                    <select value={filterDept} onChange={e => setFilterDept(e.target.value)}
                        className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="">All Departments</option>
                        {departments.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                    <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
                        className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="">All Statuses</option>
                        {(['Active', 'Expired', 'Suspended'] as CompetencyStatus[]).map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                    {(filterUser || filterDept || filterStatus) && (
                        <button onClick={() => { setFilterUser(''); setFilterDept(''); setFilterStatus(''); }}
                            className="text-sm text-slate-500 hover:text-slate-800 underline">Clear filters</button>
                    )}
                    <span className="text-xs text-slate-400 ml-auto">{filtered.length} record(s)</span>
                </div>
            </Card>

            <Card>
                <div className="p-4">
                    {loading ? <p className="text-slate-500 text-sm text-center py-8">Loading...</p> : (
                        <Table
                            data={filtered}
                            keyField="id"
                            emptyMessage="No competency records found."
                            columns={[
                                { header: 'User', accessor: r => <span className="font-medium text-slate-900">{r.userName || r.userId}</span> },
                                { header: 'Dept', accessor: r => r.userDepartment || '—' },
                                {
                                    header: 'Category / Test', accessor: r => (
                                        <span className="text-slate-600">{r.category || r.testId || '—'}</span>
                                    )
                                },
                                { header: 'Competency Date', accessor: r => r.competencyDate ? new Date(r.competencyDate).toLocaleDateString() : '—' },
                                {
                                    header: 'Expiry Date', accessor: r => (
                                        <span className={isExpiringSoon(r.expiryDate) ? 'text-amber-600 font-semibold' : ''}>
                                            {r.expiryDate ? new Date(r.expiryDate).toLocaleDateString() : '—'}
                                            {isExpiringSoon(r.expiryDate) && ' ⚠'}
                                        </span>
                                    )
                                },
                                { header: 'Assessed By', accessor: r => r.assessedBy },
                                {
                                    header: 'Status', accessor: r => (
                                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[r.status]}`}>
                                            {r.status}
                                        </span>
                                    )
                                },
                                {
                                    header: 'Actions', accessor: r => (
                                        <div className="flex gap-2">
                                            <button onClick={() => openEdit(r)} className="text-slate-400 hover:text-blue-600 transition-colors" title="Edit">
                                                <Pencil className="w-4 h-4" />
                                            </button>
                                            <button onClick={() => handleDelete(r.id)} className="text-slate-400 hover:text-red-500 transition-colors" title="Delete">
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

            {/* Form Modal */}
            {showForm && (
                <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4">
                    <div className="bg-white w-full max-w-md rounded-xl shadow-xl max-h-[90vh] overflow-y-auto">
                        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 sticky top-0 bg-white">
                            <h2 className="text-lg font-semibold text-slate-900">{editingId ? 'Edit Competency Record' : 'Add Competency Record'}</h2>
                            <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
                        </div>
                        <form onSubmit={handleSave} className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">User *</label>
                                <select required value={form.userId} onChange={e => setForm(f => ({ ...f, userId: e.target.value }))}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                                    <option value="">Select user...</option>
                                    {users.map(u => <option key={u.id} value={u.id}>{u.name} ({u.username})</option>)}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Category</label>
                                <input value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                                    placeholder="e.g. Phlebotomy, QC, Reporting"
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Specific Test (optional)</label>
                                <select value={form.testId} onChange={e => setForm(f => ({ ...f, testId: e.target.value }))}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                                    <option value="">None / Category only</option>
                                    {tests.map(t => <option key={t.id} value={t.id}>{t.name} ({t.code})</option>)}
                                </select>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Competency Date *</label>
                                    <input required type="date" value={form.competencyDate} onChange={e => setForm(f => ({ ...f, competencyDate: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Expiry Date *</label>
                                    <input required type="date" value={form.expiryDate} onChange={e => setForm(f => ({ ...f, expiryDate: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                                </div>
                            </div>
                            {editingId && (
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Status</label>
                                    <select value={editStatus || 'Active'} onChange={e => setEditStatus(e.target.value as CompetencyStatus)}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                                        {(['Active', 'Expired', 'Suspended'] as CompetencyStatus[]).map(s => <option key={s} value={s}>{s}</option>)}
                                    </select>
                                </div>
                            )}
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
