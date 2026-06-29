'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Syringe, Plus, Search, Calendar, User, MapPin, AlertTriangle, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';

type Schedule = {
    id: string;
    patientId: string;
    patientName: string;
    mrn: string;
    orderId: string | null;
    wardLocation: string;
    scheduledAt: string;
    collectionType: 'Routine' | 'STAT' | 'Timed';
    testIds: string | null;
    assignedTo: string | null;
    status: 'Scheduled' | 'InProgress' | 'Completed' | 'Cancelled';
    notes: string | null;
    completedAt: string | null;
    createdAt: string;
};

type PatientSearchResult = {
    id: string;
    firstName: string;
    lastName: string;
    mrn: string;
    dob: string;
};

type NewScheduleForm = {
    patientId: string;
    patientSearch: string;
    selectedPatientName: string;
    orderId: string;
    wardLocation: string;
    scheduledAt: string;
    collectionType: 'Routine' | 'STAT' | 'Timed';
    notes: string;
    assignedTo: string;
};

const defaultForm: NewScheduleForm = {
    patientId: '',
    patientSearch: '',
    selectedPatientName: '',
    orderId: '',
    wardLocation: '',
    scheduledAt: '',
    collectionType: 'Routine',
    notes: '',
    assignedTo: '',
};

const statusConfig: Record<string, { label: string; classes: string; icon: React.ReactNode }> = {
    Scheduled: { label: 'Scheduled', classes: 'bg-blue-100 text-blue-700', icon: <Calendar className="h-3 w-3" /> },
    InProgress: { label: 'In Progress', classes: 'bg-amber-100 text-amber-700', icon: <Loader2 className="h-3 w-3" /> },
    Completed: { label: 'Completed', classes: 'bg-green-100 text-green-700', icon: <CheckCircle className="h-3 w-3" /> },
    Cancelled: { label: 'Cancelled', classes: 'bg-slate-100 text-slate-500', icon: <XCircle className="h-3 w-3" /> },
};

function StatusBadge({ status }: { status: string }) {
    const cfg = statusConfig[status] || { label: status, classes: 'bg-slate-100 text-slate-600', icon: null };
    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.classes}`}>
            {cfg.icon}{cfg.label}
        </span>
    );
}

function CollectionTypeBadge({ type }: { type: string }) {
    const map: Record<string, string> = {
        'STAT': 'bg-red-100 text-red-700',
        'Timed': 'bg-purple-100 text-purple-700',
        'Routine': 'bg-slate-100 text-slate-600',
    };
    return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${map[type] || 'bg-slate-100 text-slate-600'}`}>
            {type}
        </span>
    );
}

export default function PhlebotomyPage() {
    const [schedules, setSchedules] = useState<Schedule[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedSchedule, setSelectedSchedule] = useState<Schedule | null>(null);
    const [showNewForm, setShowNewForm] = useState(false);

    // Filters
    const [filterDate, setFilterDate] = useState('');
    const [filterStatus, setFilterStatus] = useState('');

    // New schedule form
    const [form, setForm] = useState<NewScheduleForm>(defaultForm);
    const [patientResults, setPatientResults] = useState<PatientSearchResult[]>([]);
    const [searchingPatients, setSearchingPatients] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [formError, setFormError] = useState('');

    const loadSchedules = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (filterDate) params.set('date', filterDate);
            if (filterStatus) params.set('status', filterStatus);
            const res = await fetch(`/api/phlebotomy?${params.toString()}`);
            if (res.ok) setSchedules(await res.json());
        } catch (err) {
            console.error('Error loading schedules:', err);
        } finally {
            setLoading(false);
        }
    }, [filterDate, filterStatus]);

    useEffect(() => {
        loadSchedules();
    }, [loadSchedules]);

    const searchPatients = useCallback(async (query: string) => {
        if (query.length < 2) { setPatientResults([]); return; }
        setSearchingPatients(true);
        try {
            const res = await fetch(`/api/patients?search=${encodeURIComponent(query)}`);
            if (res.ok) setPatientResults(await res.json());
        } catch (err) {
            console.error('Error searching patients:', err);
        } finally {
            setSearchingPatients(false);
        }
    }, []);

    useEffect(() => {
        const t = setTimeout(() => searchPatients(form.patientSearch), 300);
        return () => clearTimeout(t);
    }, [form.patientSearch, searchPatients]);

    const handleSelectPatient = (p: PatientSearchResult) => {
        setForm(f => ({
            ...f,
            patientId: p.id,
            patientSearch: `${p.firstName} ${p.lastName} (${p.mrn})`,
            selectedPatientName: `${p.firstName} ${p.lastName}`,
        }));
        setPatientResults([]);
    };

    const handleSubmitNew = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!form.patientId) { setFormError('Please select a patient'); return; }
        setSubmitting(true);
        setFormError('');
        try {
            const res = await fetch('/api/phlebotomy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    patientId: form.patientId,
                    orderId: form.orderId || undefined,
                    wardLocation: form.wardLocation,
                    scheduledAt: form.scheduledAt,
                    collectionType: form.collectionType,
                    notes: form.notes || undefined,
                    assignedTo: form.assignedTo || undefined,
                }),
            });
            if (!res.ok) {
                const d = await res.json();
                setFormError(d.error || 'Failed to create schedule');
                return;
            }
            setForm(defaultForm);
            setShowNewForm(false);
            await loadSchedules();
        } catch {
            setFormError('Network error. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    const handleStatusUpdate = async (id: string, status: Schedule['status']) => {
        try {
            const res = await fetch(`/api/phlebotomy/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status }),
            });
            if (res.ok) {
                await loadSchedules();
                // Refresh selected
                setSelectedSchedule(prev => prev && prev.id === id ? { ...prev, status, completedAt: status === 'Completed' ? new Date().toISOString() : prev.completedAt } : prev);
            }
        } catch (err) {
            console.error('Error updating status:', err);
        }
    };

    const handleCancel = async (id: string) => {
        if (!confirm('Cancel this phlebotomy schedule?')) return;
        await handleStatusUpdate(id, 'Cancelled');
        if (selectedSchedule?.id === id) setSelectedSchedule(null);
    };

    const formatDateTime = (iso: string) => {
        if (!iso) return '—';
        return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    };

    const formatDate = (iso: string) => {
        if (!iso) return '—';
        return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };

    return (
        <div className="p-6 max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-red-50 rounded-lg">
                        <Syringe className="h-6 w-6 text-red-600" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">Phlebotomy Scheduling</h1>
                        <p className="text-sm text-slate-500">Manage specimen collection schedules and ward visits</p>
                    </div>
                </div>
                <button
                    onClick={() => { setShowNewForm(true); setForm(defaultForm); setFormError(''); }}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
                >
                    <Plus className="h-4 w-4" /> New Schedule
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                {/* Left: Schedule List */}
                <div className="lg:col-span-2 space-y-4">
                    {/* Filters */}
                    <Card>
                        <div className="flex gap-2 flex-wrap">
                            <div className="flex items-center gap-1.5 flex-1 min-w-32">
                                <Calendar className="h-4 w-4 text-slate-400 flex-shrink-0" />
                                <input
                                    type="date"
                                    value={filterDate}
                                    onChange={e => setFilterDate(e.target.value)}
                                    className="flex-1 border border-slate-300 rounded-md px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                            <select
                                value={filterStatus}
                                onChange={e => setFilterStatus(e.target.value)}
                                className="border border-slate-300 rounded-md px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                            >
                                <option value="">All Statuses</option>
                                <option value="Scheduled">Scheduled</option>
                                <option value="InProgress">In Progress</option>
                                <option value="Completed">Completed</option>
                                <option value="Cancelled">Cancelled</option>
                            </select>
                            {(filterDate || filterStatus) && (
                                <button onClick={() => { setFilterDate(''); setFilterStatus(''); }} className="text-xs text-blue-600 hover:underline">
                                    Clear
                                </button>
                            )}
                        </div>
                    </Card>

                    {/* Schedule List */}
                    <Card>
                        {loading ? (
                            <div className="flex items-center justify-center py-12 text-slate-400">
                                <Clock className="h-4 w-4 animate-spin mr-2" /> Loading...
                            </div>
                        ) : schedules.length === 0 ? (
                            <div className="text-center py-10 text-slate-400 text-sm">
                                No schedules found{filterDate || filterStatus ? ' for the selected filters' : ''}.
                            </div>
                        ) : (
                            <div className="divide-y divide-slate-100 -mx-6 -mb-6">
                                {schedules.map(s => (
                                    <button
                                        key={s.id}
                                        onClick={() => setSelectedSchedule(s)}
                                        className={`w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors ${selectedSchedule?.id === s.id ? 'bg-blue-50 border-l-2 border-blue-500' : ''}`}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="min-w-0">
                                                <div className="flex items-center gap-1.5 flex-wrap">
                                                    <span className="font-medium text-sm text-slate-800 truncate">{s.patientName}</span>
                                                    <CollectionTypeBadge type={s.collectionType} />
                                                </div>
                                                <div className="flex items-center gap-1 text-xs text-slate-500 mt-0.5">
                                                    <MapPin className="h-3 w-3 flex-shrink-0" />
                                                    <span className="truncate">{s.wardLocation}</span>
                                                </div>
                                                <div className="flex items-center gap-1 text-xs text-slate-500 mt-0.5">
                                                    <Calendar className="h-3 w-3 flex-shrink-0" />
                                                    {formatDateTime(s.scheduledAt)}
                                                </div>
                                            </div>
                                            <div className="flex-shrink-0">
                                                <StatusBadge status={s.status} />
                                            </div>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}
                    </Card>
                </div>

                {/* Right: Detail / New Form */}
                <div className="lg:col-span-3">
                    {showNewForm ? (
                        <Card title="New Phlebotomy Schedule">
                            {formError && (
                                <div className="flex items-center gap-2 p-3 mb-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                                    <AlertTriangle className="h-4 w-4 flex-shrink-0" /> {formError}
                                </div>
                            )}
                            <form onSubmit={handleSubmitNew} className="space-y-4">
                                {/* Patient Search */}
                                <div className="relative">
                                    <label className="block text-xs font-medium text-slate-700 mb-1">Patient *</label>
                                    <div className="relative">
                                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                        <input
                                            type="text"
                                            value={form.patientSearch}
                                            onChange={e => {
                                                setForm(f => ({ ...f, patientSearch: e.target.value, patientId: '', selectedPatientName: '' }));
                                            }}
                                            placeholder="Search by name or MRN..."
                                            className="w-full border border-slate-300 rounded-md pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            autoComplete="off"
                                        />
                                        {searchingPatients && (
                                            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 animate-spin" />
                                        )}
                                    </div>
                                    {patientResults.length > 0 && (
                                        <div className="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-y-auto">
                                            {patientResults.map(p => (
                                                <button
                                                    key={p.id}
                                                    type="button"
                                                    onClick={() => handleSelectPatient(p)}
                                                    className="w-full text-left px-3 py-2 hover:bg-blue-50 text-sm"
                                                >
                                                    <div className="font-medium text-slate-800">{p.firstName} {p.lastName}</div>
                                                    <div className="text-xs text-slate-500">MRN: {p.mrn} · DOB: {p.dob}</div>
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                    {form.patientId && (
                                        <div className="flex items-center gap-1 mt-1 text-xs text-green-700">
                                            <CheckCircle className="h-3 w-3" /> {form.selectedPatientName} selected
                                        </div>
                                    )}
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-xs font-medium text-slate-700 mb-1">Ward Location *</label>
                                        <input
                                            type="text"
                                            value={form.wardLocation}
                                            onChange={e => setForm(f => ({ ...f, wardLocation: e.target.value }))}
                                            placeholder="e.g. Ward 4B"
                                            required
                                            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium text-slate-700 mb-1">Collection Type *</label>
                                        <select
                                            value={form.collectionType}
                                            onChange={e => setForm(f => ({ ...f, collectionType: e.target.value as NewScheduleForm['collectionType'] }))}
                                            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                                            required
                                        >
                                            <option value="Routine">Routine</option>
                                            <option value="STAT">STAT</option>
                                            <option value="Timed">Timed</option>
                                        </select>
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-xs font-medium text-slate-700 mb-1">Scheduled Date &amp; Time *</label>
                                        <input
                                            type="datetime-local"
                                            value={form.scheduledAt}
                                            onChange={e => setForm(f => ({ ...f, scheduledAt: e.target.value }))}
                                            required
                                            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium text-slate-700 mb-1">Assigned To</label>
                                        <input
                                            type="text"
                                            value={form.assignedTo}
                                            onChange={e => setForm(f => ({ ...f, assignedTo: e.target.value }))}
                                            placeholder="Phlebotomist name"
                                            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-xs font-medium text-slate-700 mb-1">Notes</label>
                                    <textarea
                                        value={form.notes}
                                        onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                                        placeholder="Any special instructions or notes..."
                                        rows={2}
                                        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                                    />
                                </div>

                                <div className="flex gap-2 pt-1">
                                    <button
                                        type="submit"
                                        disabled={submitting}
                                        className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
                                    >
                                        {submitting ? 'Saving...' : 'Create Schedule'}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setShowNewForm(false)}
                                        className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-md text-sm font-medium hover:bg-slate-50 transition-colors"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </form>
                        </Card>
                    ) : selectedSchedule ? (
                        <Card>
                            <div className="space-y-4">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <h2 className="text-lg font-semibold text-slate-900">{selectedSchedule.patientName}</h2>
                                            <StatusBadge status={selectedSchedule.status} />
                                            <CollectionTypeBadge type={selectedSchedule.collectionType} />
                                        </div>
                                        <div className="text-sm text-slate-500 mt-0.5">MRN: {selectedSchedule.mrn}</div>
                                    </div>
                                    <button
                                        onClick={() => setSelectedSchedule(null)}
                                        className="p-1 text-slate-400 hover:text-slate-600"
                                    >
                                        <XCircle className="h-5 w-5" />
                                    </button>
                                </div>

                                <div className="grid grid-cols-2 gap-3 text-sm">
                                    <div>
                                        <div className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-0.5">Ward / Location</div>
                                        <div className="flex items-center gap-1 text-slate-800">
                                            <MapPin className="h-4 w-4 text-slate-400" />
                                            {selectedSchedule.wardLocation}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-0.5">Scheduled At</div>
                                        <div className="flex items-center gap-1 text-slate-800">
                                            <Calendar className="h-4 w-4 text-slate-400" />
                                            {formatDateTime(selectedSchedule.scheduledAt)}
                                        </div>
                                    </div>
                                    {selectedSchedule.assignedTo && (
                                        <div>
                                            <div className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-0.5">Assigned To</div>
                                            <div className="flex items-center gap-1 text-slate-800">
                                                <User className="h-4 w-4 text-slate-400" />
                                                {selectedSchedule.assignedTo}
                                            </div>
                                        </div>
                                    )}
                                    {selectedSchedule.completedAt && (
                                        <div>
                                            <div className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-0.5">Completed At</div>
                                            <div className="flex items-center gap-1 text-green-700">
                                                <CheckCircle className="h-4 w-4" />
                                                {formatDateTime(selectedSchedule.completedAt)}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {selectedSchedule.notes && (
                                    <div className="p-3 bg-slate-50 rounded-lg text-sm text-slate-700">
                                        <div className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-1">Notes</div>
                                        {selectedSchedule.notes}
                                    </div>
                                )}

                                {/* Status Action Buttons */}
                                {selectedSchedule.status !== 'Completed' && selectedSchedule.status !== 'Cancelled' && (
                                    <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-100">
                                        {selectedSchedule.status === 'Scheduled' && (
                                            <button
                                                onClick={() => handleStatusUpdate(selectedSchedule.id, 'InProgress')}
                                                className="flex items-center gap-2 px-4 py-2 bg-amber-500 text-white rounded-md text-sm font-medium hover:bg-amber-600 transition-colors"
                                            >
                                                <Loader2 className="h-4 w-4" /> Start Collection
                                            </button>
                                        )}
                                        {selectedSchedule.status === 'InProgress' && (
                                            <button
                                                onClick={() => handleStatusUpdate(selectedSchedule.id, 'Completed')}
                                                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 transition-colors"
                                            >
                                                <CheckCircle className="h-4 w-4" /> Mark Completed
                                            </button>
                                        )}
                                        <button
                                            onClick={() => handleCancel(selectedSchedule.id)}
                                            className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-md text-sm font-medium hover:bg-slate-50 transition-colors"
                                        >
                                            <XCircle className="h-4 w-4" /> Cancel
                                        </button>
                                    </div>
                                )}

                                <div className="text-xs text-slate-400 pt-1">
                                    Created: {formatDate(selectedSchedule.createdAt)}
                                </div>
                            </div>
                        </Card>
                    ) : (
                        <Card>
                            <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-3">
                                <Syringe className="h-10 w-10 text-slate-300" />
                                <div className="text-sm text-center">
                                    <div className="font-medium text-slate-500">No schedule selected</div>
                                    <div>Click a schedule on the left to view details, or create a new one.</div>
                                </div>
                            </div>
                        </Card>
                    )}
                </div>
            </div>
        </div>
    );
}
