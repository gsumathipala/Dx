'use client';

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { AlertTriangle, ChevronRight, Clock, CheckCircle, Send, XCircle, RefreshCw } from 'lucide-react';

interface EpiNotification {
    id: string;
    orderId: string;
    patientId: string;
    conditionId: string;
    detectedAt: string;
    status: 'Pending' | 'Reviewed' | 'Submitted' | 'Closed';
    reviewedBy: string | null;
    reviewedAt: string | null;
    submittedBy: string | null;
    submittedAt: string | null;
    notes: string | null;
    condition: {
        id: string;
        name: string;
        organism: string | null;
        reportingBody: string;
        timeframe: string;
    } | null;
    patient: {
        id: string;
        name: string;
        mrn: string;
        dob: string;
        gender: string;
    } | null;
    order: {
        id: string;
        accessionNumber: string;
        timestamp: string;
        status: string;
    } | null;
}

const STATUS_CONFIG = {
    Pending: { color: 'bg-amber-100 text-amber-700 border-amber-200', icon: Clock, label: 'Pending' },
    Reviewed: { color: 'bg-blue-100 text-blue-700 border-blue-200', icon: CheckCircle, label: 'Reviewed' },
    Submitted: { color: 'bg-emerald-100 text-emerald-700 border-emerald-200', icon: Send, label: 'Submitted' },
    Closed: { color: 'bg-slate-100 text-slate-600 border-slate-200', icon: XCircle, label: 'Closed' },
};

const STATUS_ORDER: EpiNotification['status'][] = ['Pending', 'Reviewed', 'Submitted', 'Closed'];

function StatusBadge({ status }: { status: EpiNotification['status'] }) {
    const cfg = STATUS_CONFIG[status];
    const Icon = cfg.icon;
    return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${cfg.color}`}>
            <Icon size={11} />
            {cfg.label}
        </span>
    );
}

export default function EpidemiologyPage() {
    const [notifications, setNotifications] = useState<EpiNotification[]>([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState<EpiNotification | null>(null);
    const [notes, setNotes] = useState('');
    const [updating, setUpdating] = useState(false);
    const [filterStatus, setFilterStatus] = useState<EpiNotification['status'] | 'All'>('All');

    const load = () =>
        fetch('/api/epidemiology')
            .then((r) => r.json())
            .then((data) => {
                const arr = Array.isArray(data) ? data : [];
                setNotifications(arr);
                // Re-sync selected if it exists
                if (selected) {
                    const updated = arr.find((n: EpiNotification) => n.id === selected.id);
                    if (updated) {
                        setSelected(updated);
                        setNotes(updated.notes ?? '');
                    }
                }
            })
            .finally(() => setLoading(false));

    useEffect(() => { load(); }, []);

    const handleSelect = (n: EpiNotification) => {
        setSelected(n);
        setNotes(n.notes ?? '');
    };

    const handleAction = async (newStatus: EpiNotification['status']) => {
        if (!selected) return;
        setUpdating(true);
        try {
            await fetch(`/api/epidemiology/${selected.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus, notes }),
            });
            await load();
        } finally {
            setUpdating(false);
        }
    };

    const grouped = STATUS_ORDER.reduce((acc, s) => {
        acc[s] = notifications.filter((n) => n.status === s);
        return acc;
    }, {} as Record<EpiNotification['status'], EpiNotification[]>);

    const displayList =
        filterStatus === 'All'
            ? notifications
            : notifications.filter((n) => n.status === filterStatus);

    return (
        <div className="min-h-screen bg-slate-50 p-6">
            <div className="max-w-7xl mx-auto">
                <div className="mb-6 flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">Epidemiology Notifications</h1>
                        <p className="text-slate-500 text-sm mt-1">Manage notifiable disease reporting workflow</p>
                    </div>
                    <button
                        onClick={() => { setLoading(true); load(); }}
                        className="flex items-center gap-2 px-3 py-2 text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-100 text-sm"
                    >
                        <RefreshCw size={14} />
                        Refresh
                    </button>
                </div>

                <div className="flex gap-6 min-h-[600px]">
                    {/* Left panel */}
                    <div className="w-80 flex-shrink-0 space-y-3">
                        {/* Status filter tabs */}
                        <div className="flex flex-wrap gap-1">
                            {(['All', ...STATUS_ORDER] as const).map((s) => (
                                <button
                                    key={s}
                                    onClick={() => setFilterStatus(s)}
                                    className={`px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
                                        filterStatus === s
                                            ? 'bg-slate-700 text-white border-slate-700'
                                            : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                                    }`}
                                >
                                    {s}
                                    {s !== 'All' && (
                                        <span className="ml-1 opacity-70">({grouped[s as EpiNotification['status']]?.length ?? 0})</span>
                                    )}
                                </button>
                            ))}
                        </div>

                        {loading ? (
                            <div className="text-center py-10 text-slate-400 text-sm">Loading...</div>
                        ) : displayList.length === 0 ? (
                            <div className="text-center py-10 text-slate-400 text-sm bg-white rounded-xl border border-slate-200">
                                <AlertTriangle size={32} className="mx-auto mb-2 opacity-20" />
                                No notifications found.
                            </div>
                        ) : (
                            <div className="space-y-2 overflow-y-auto max-h-[calc(100vh-220px)]">
                                {displayList.map((n) => (
                                    <button
                                        key={n.id}
                                        onClick={() => handleSelect(n)}
                                        className={`w-full text-left p-3.5 rounded-xl border transition-all ${
                                            selected?.id === n.id
                                                ? 'border-blue-300 bg-blue-50 shadow-sm'
                                                : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                                        }`}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="min-w-0">
                                                <p className="font-medium text-slate-900 text-sm truncate">
                                                    {n.condition?.name ?? 'Unknown Condition'}
                                                </p>
                                                <p className="text-xs text-slate-500 mt-0.5 truncate">
                                                    {n.patient?.name ?? 'Unknown Patient'} · MRN {n.patient?.mrn}
                                                </p>
                                                <p className="text-xs text-slate-400 mt-1">
                                                    {new Date(n.detectedAt).toLocaleDateString()}
                                                </p>
                                            </div>
                                            <div className="flex-shrink-0 flex flex-col items-end gap-1">
                                                <StatusBadge status={n.status} />
                                                <ChevronRight size={14} className="text-slate-300" />
                                            </div>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Right panel — Detail */}
                    <div className="flex-1 min-w-0">
                        {!selected ? (
                            <div className="h-full flex items-center justify-center bg-white rounded-xl border border-slate-200">
                                <div className="text-center text-slate-400">
                                    <AlertTriangle size={40} className="mx-auto mb-3 opacity-20" />
                                    <p className="text-sm">Select a notification to view details</p>
                                </div>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {/* Condition */}
                                <Card title="Condition Details">
                                    <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                                        <div>
                                            <p className="text-xs text-slate-400 uppercase font-semibold">Condition</p>
                                            <p className="text-slate-900 font-medium mt-0.5">{selected.condition?.name ?? '—'}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-slate-400 uppercase font-semibold">Organism</p>
                                            <p className="text-slate-900 mt-0.5">{selected.condition?.organism ?? '—'}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-slate-400 uppercase font-semibold">Reporting Body</p>
                                            <p className="text-slate-900 mt-0.5">{selected.condition?.reportingBody ?? '—'}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-slate-400 uppercase font-semibold">Timeframe</p>
                                            <p className="text-slate-900 mt-0.5">{selected.condition?.timeframe ?? '—'}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-slate-400 uppercase font-semibold">Detected At</p>
                                            <p className="text-slate-900 mt-0.5">{new Date(selected.detectedAt).toLocaleString()}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-slate-400 uppercase font-semibold">Status</p>
                                            <div className="mt-0.5"><StatusBadge status={selected.status} /></div>
                                        </div>
                                    </div>
                                </Card>

                                {/* Patient */}
                                <Card title="Patient Information">
                                    {selected.patient ? (
                                        <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                                            <div>
                                                <p className="text-xs text-slate-400 uppercase font-semibold">Name</p>
                                                <p className="text-slate-900 font-medium mt-0.5">{selected.patient.name}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs text-slate-400 uppercase font-semibold">MRN</p>
                                                <p className="text-slate-900 font-mono mt-0.5">{selected.patient.mrn}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs text-slate-400 uppercase font-semibold">DOB</p>
                                                <p className="text-slate-900 mt-0.5">{selected.patient.dob}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs text-slate-400 uppercase font-semibold">Gender</p>
                                                <p className="text-slate-900 mt-0.5">{selected.patient.gender}</p>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-slate-400 text-sm">Patient data unavailable</p>
                                    )}
                                </Card>

                                {/* Order */}
                                <Card title="Order Information">
                                    {selected.order ? (
                                        <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                                            <div>
                                                <p className="text-xs text-slate-400 uppercase font-semibold">Accession #</p>
                                                <p className="text-slate-900 font-mono mt-0.5">{selected.order.accessionNumber}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs text-slate-400 uppercase font-semibold">Order Status</p>
                                                <p className="text-slate-900 mt-0.5">{selected.order.status}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs text-slate-400 uppercase font-semibold">Order Date</p>
                                                <p className="text-slate-900 mt-0.5">{new Date(selected.order.timestamp).toLocaleString()}</p>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-slate-400 text-sm">Order data unavailable</p>
                                    )}
                                </Card>

                                {/* Audit Trail */}
                                {(selected.reviewedBy || selected.submittedBy) && (
                                    <Card title="Audit Trail">
                                        <div className="space-y-2">
                                            {selected.reviewedBy && (
                                                <div className="flex items-center gap-2 text-sm">
                                                    <CheckCircle size={14} className="text-blue-500" />
                                                    <span className="text-slate-600">
                                                        Reviewed by <strong>{selected.reviewedBy}</strong> on{' '}
                                                        {selected.reviewedAt ? new Date(selected.reviewedAt).toLocaleString() : '—'}
                                                    </span>
                                                </div>
                                            )}
                                            {selected.submittedBy && (
                                                <div className="flex items-center gap-2 text-sm">
                                                    <Send size={14} className="text-emerald-500" />
                                                    <span className="text-slate-600">
                                                        Submitted by <strong>{selected.submittedBy}</strong> on{' '}
                                                        {selected.submittedAt ? new Date(selected.submittedAt).toLocaleString() : '—'}
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    </Card>
                                )}

                                {/* Notes + Actions */}
                                {selected.status !== 'Closed' && (
                                    <Card title="Actions">
                                        <div className="space-y-4">
                                            <div>
                                                <label className="block text-xs font-medium text-slate-600 mb-1">Notes</label>
                                                <textarea
                                                    value={notes}
                                                    onChange={(e) => setNotes(e.target.value)}
                                                    rows={3}
                                                    placeholder="Add notes about this notification..."
                                                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none"
                                                />
                                            </div>
                                            <div className="flex gap-2 flex-wrap">
                                                {selected.status === 'Pending' && (
                                                    <button
                                                        onClick={() => handleAction('Reviewed')}
                                                        disabled={updating}
                                                        className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
                                                    >
                                                        <CheckCircle size={15} />
                                                        Mark Reviewed
                                                    </button>
                                                )}
                                                {selected.status === 'Reviewed' && (
                                                    <button
                                                        onClick={() => handleAction('Submitted')}
                                                        disabled={updating}
                                                        className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 text-sm font-medium disabled:opacity-50"
                                                    >
                                                        <Send size={15} />
                                                        Submit to Authorities
                                                    </button>
                                                )}
                                                {selected.status === 'Submitted' && (
                                                    <button
                                                        onClick={() => handleAction('Closed')}
                                                        disabled={updating}
                                                        className="flex items-center gap-2 px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 text-sm font-medium disabled:opacity-50"
                                                    >
                                                        <XCircle size={15} />
                                                        Close
                                                    </button>
                                                )}
                                                {/* Allow saving notes at any active status */}
                                                <button
                                                    onClick={() => handleAction(selected.status)}
                                                    disabled={updating}
                                                    className="flex items-center gap-2 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 text-sm disabled:opacity-50"
                                                >
                                                    Save Notes
                                                </button>
                                            </div>
                                        </div>
                                    </Card>
                                )}

                                {selected.status === 'Closed' && selected.notes && (
                                    <Card title="Notes">
                                        <p className="text-sm text-slate-700 whitespace-pre-wrap">{selected.notes}</p>
                                    </Card>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
