'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Table } from '@/components/ui/Table';
import { Plus, Pencil, UserMinus, Search, X } from 'lucide-react';

type RequesterType = 'GP' | 'Ward' | 'Clinic' | 'Hospital' | 'External';
type DeliveryPreference = 'portal' | 'email' | 'print' | 'fax';

interface Requester {
    id: string;
    name: string;
    type: RequesterType;
    contactName: string | null;
    email: string | null;
    phone: string | null;
    fax: string | null;
    address: string | null;
    deliveryPreference: DeliveryPreference;
    active: boolean;
    createdAt: string;
    notes: string | null;
}

const TYPE_COLORS: Record<RequesterType, string> = {
    GP: 'bg-blue-100 text-blue-800',
    Ward: 'bg-purple-100 text-purple-800',
    Clinic: 'bg-teal-100 text-teal-800',
    Hospital: 'bg-orange-100 text-orange-800',
    External: 'bg-slate-100 text-slate-700',
};

const DELIVERY_LABELS: Record<DeliveryPreference, string> = {
    portal: 'Portal',
    email: 'Email',
    print: 'Print',
    fax: 'Fax',
};

const BLANK_FORM = {
    name: '', type: 'GP' as RequesterType, contactName: '', email: '',
    phone: '', fax: '', address: '', deliveryPreference: 'portal' as DeliveryPreference, notes: '',
};

export default function RequestersAdminPage() {
    const [requesters, setRequesters] = useState<Requester[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [tab, setTab] = useState<'all' | 'active' | 'inactive'>('all');
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [form, setForm] = useState(BLANK_FORM);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/requesters');
            if (res.ok) setRequesters(await res.json());
        } catch (e) {
            setMessage('Failed to load requesters');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const filtered = requesters
        .filter(r => tab === 'all' ? true : tab === 'active' ? r.active : !r.active)
        .filter(r =>
            !search ||
            r.name.toLowerCase().includes(search.toLowerCase()) ||
            (r.contactName || '').toLowerCase().includes(search.toLowerCase()) ||
            (r.email || '').toLowerCase().includes(search.toLowerCase())
        );

    const openAdd = () => {
        setForm(BLANK_FORM);
        setEditingId(null);
        setShowForm(true);
    };

    const openEdit = (r: Requester) => {
        setForm({
            name: r.name, type: r.type, contactName: r.contactName || '',
            email: r.email || '', phone: r.phone || '', fax: r.fax || '',
            address: r.address || '', deliveryPreference: r.deliveryPreference, notes: r.notes || '',
        });
        setEditingId(r.id);
        setShowForm(true);
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            const url = editingId ? `/api/requesters/${editingId}` : '/api/requesters';
            const method = editingId ? 'PUT' : 'POST';
            const res = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form),
            });
            if (!res.ok) {
                const err = await res.json();
                setMessage(err.error || 'Save failed');
            } else {
                setMessage(editingId ? 'Requester updated' : 'Requester created');
                setShowForm(false);
                load();
            }
        } finally {
            setSaving(false);
        }
    };

    const handleDeactivate = async (id: string, active: boolean) => {
        if (!active && !confirm('Re-activate this requester?')) return;
        if (active && !confirm('Deactivate this requester?')) return;
        const res = await fetch(`/api/requesters/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: !active }),
        });
        if (res.ok) { setMessage(active ? 'Requester deactivated' : 'Requester reactivated'); load(); }
    };

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Requester / Client Registry</h1>
                    <p className="text-sm text-slate-500 mt-1">Manage GP surgeries, wards, clinics and external clients</p>
                </div>
                <button
                    onClick={openAdd}
                    className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                    <Plus className="w-4 h-4" /> Add Requester
                </button>
            </div>

            {message && (
                <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-2 rounded-lg text-sm flex justify-between">
                    {message}
                    <button onClick={() => setMessage('')}><X className="w-4 h-4" /></button>
                </div>
            )}

            <Card>
                <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
                    <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
                        {(['all', 'active', 'inactive'] as const).map(t => (
                            <button
                                key={t}
                                onClick={() => setTab(t)}
                                className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${tab === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
                            >
                                {t}
                            </button>
                        ))}
                    </div>
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search name, contact, email..."
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            className="pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
                        />
                    </div>
                </div>
                <div className="p-4">
                    {loading ? (
                        <p className="text-slate-500 text-sm text-center py-8">Loading...</p>
                    ) : (
                        <Table
                            data={filtered}
                            keyField="id"
                            emptyMessage="No requesters found."
                            columns={[
                                {
                                    header: 'Name',
                                    accessor: (r) => <span className="font-medium text-slate-900">{r.name}</span>,
                                },
                                {
                                    header: 'Type',
                                    accessor: (r) => (
                                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[r.type]}`}>
                                            {r.type}
                                        </span>
                                    ),
                                },
                                { header: 'Contact', accessor: (r) => r.contactName || '—' },
                                { header: 'Email', accessor: (r) => r.email || '—' },
                                { header: 'Phone', accessor: (r) => r.phone || '—' },
                                {
                                    header: 'Delivery',
                                    accessor: (r) => (
                                        <span className="inline-flex px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600">
                                            {DELIVERY_LABELS[r.deliveryPreference]}
                                        </span>
                                    ),
                                },
                                {
                                    header: 'Status',
                                    accessor: (r) => (
                                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${r.active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                            {r.active ? 'Active' : 'Inactive'}
                                        </span>
                                    ),
                                },
                                {
                                    header: 'Actions',
                                    accessor: (r) => (
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => openEdit(r)}
                                                className="text-slate-400 hover:text-blue-600 transition-colors"
                                                title="Edit"
                                            >
                                                <Pencil className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={() => handleDeactivate(r.id, r.active)}
                                                className={`transition-colors ${r.active ? 'text-slate-400 hover:text-red-500' : 'text-slate-400 hover:text-green-600'}`}
                                                title={r.active ? 'Deactivate' : 'Reactivate'}
                                            >
                                                <UserMinus className="w-4 h-4" />
                                            </button>
                                        </div>
                                    ),
                                },
                            ]}
                        />
                    )}
                </div>
            </Card>

            {/* Side Panel Form */}
            {showForm && (
                <div className="fixed inset-0 bg-black/30 z-40 flex justify-end">
                    <div className="bg-white w-full max-w-lg shadow-xl flex flex-col h-full">
                        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                            <h2 className="text-lg font-semibold text-slate-900">
                                {editingId ? 'Edit Requester' : 'Add Requester'}
                            </h2>
                            <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-700">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <form onSubmit={handleSave} className="flex-1 overflow-y-auto p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Name *</label>
                                <input
                                    required
                                    value={form.name}
                                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Type *</label>
                                <select
                                    value={form.type}
                                    onChange={e => setForm(f => ({ ...f, type: e.target.value as RequesterType }))}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                    {(['GP', 'Ward', 'Clinic', 'Hospital', 'External'] as RequesterType[]).map(t => (
                                        <option key={t} value={t}>{t}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Contact Name</label>
                                <input
                                    value={form.contactName}
                                    onChange={e => setForm(f => ({ ...f, contactName: e.target.value }))}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                                    <input
                                        type="email"
                                        value={form.email}
                                        onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Phone</label>
                                    <input
                                        value={form.phone}
                                        onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Fax</label>
                                    <input
                                        value={form.fax}
                                        onChange={e => setForm(f => ({ ...f, fax: e.target.value }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Delivery Preference</label>
                                    <select
                                        value={form.deliveryPreference}
                                        onChange={e => setForm(f => ({ ...f, deliveryPreference: e.target.value as DeliveryPreference }))}
                                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    >
                                        {(['portal', 'email', 'print', 'fax'] as DeliveryPreference[]).map(d => (
                                            <option key={d} value={d}>{DELIVERY_LABELS[d]}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Address</label>
                                <textarea
                                    rows={2}
                                    value={form.address}
                                    onChange={e => setForm(f => ({ ...f, address: e.target.value }))}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Notes</label>
                                <textarea
                                    rows={2}
                                    value={form.notes}
                                    onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium transition-colors"
                                >
                                    {saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setShowForm(false)}
                                    className="flex-1 border border-slate-200 hover:bg-slate-50 text-slate-700 py-2 rounded-lg text-sm font-medium transition-colors"
                                >
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
