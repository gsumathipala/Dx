'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { AlertTriangle, Bell, X, CheckCircle } from 'lucide-react';

interface CriticalNotification {
    id: string;
    orderId: string;
    patientId: string;
    testId: string;
    testCode: string;
    value: string;
    threshold: string;
    criticalType: 'HIGH' | 'LOW';
    status: 'Pending' | 'Acknowledged' | 'Escalated';
    createdAt: string;
    createdBy?: string;
    // enriched
    patientName?: string;
    mrn?: string;
    accessionNumber?: string;
}

interface AckForm {
    notifiedClinician: string;
    notificationMethod: 'phone' | 'fax' | 'in-person';
    notes: string;
}

const DEFAULT_ACK_FORM: AckForm = {
    notifiedClinician: '',
    notificationMethod: 'phone',
    notes: '',
};

export default function CriticalValuesPage() {
    const [notifications, setNotifications] = useState<CriticalNotification[]>([]);
    const [loading, setLoading] = useState(true);
    const [ackingId, setAckingId] = useState<string | null>(null);
    const [ackForm, setAckForm] = useState<AckForm>(DEFAULT_ACK_FORM);
    const [submitting, setSubmitting] = useState(false);
    const [message, setMessage] = useState('');

    const loadNotifications = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/critical-values?status=Pending');
            if (res.ok) {
                setNotifications(await res.json());
            } else {
                setMessage('Error: Failed to load notifications.');
            }
        } catch {
            setMessage('Error: Network error loading notifications.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadNotifications();
        // Auto-refresh every 60 seconds
        const interval = setInterval(loadNotifications, 60_000);
        return () => clearInterval(interval);
    }, [loadNotifications]);

    const openAck = (id: string) => {
        setAckingId(id);
        setAckForm(DEFAULT_ACK_FORM);
    };

    const closeAck = () => {
        setAckingId(null);
        setAckForm(DEFAULT_ACK_FORM);
    };

    const handleAckSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!ackingId) return;
        if (!ackForm.notifiedClinician) {
            setMessage('Error: Notified clinician name is required.');
            return;
        }
        setSubmitting(true);
        try {
            const res = await fetch(`/api/critical-values/${ackingId}/ack`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(ackForm),
            });
            if (res.ok) {
                setNotifications(prev => prev.filter(n => n.id !== ackingId));
                closeAck();
                setMessage('Critical value acknowledged successfully.');
            } else {
                const data = await res.json();
                setMessage('Error: ' + (data.error || 'Failed to acknowledge.'));
            }
        } catch {
            setMessage('Error: Network error.');
        } finally {
            setSubmitting(false);
        }
    };

    const formatTime = (iso: string) => {
        try {
            return new Date(iso).toLocaleString();
        } catch {
            return iso;
        }
    };

    const pendingCount = notifications.length;

    return (
        <div className="max-w-6xl space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
                        <Bell className="w-7 h-7 text-red-600" />
                        Critical Value Notifications
                        {pendingCount > 0 && (
                            <span className="ml-2 inline-flex items-center justify-center px-2.5 py-0.5 rounded-full text-sm font-bold bg-red-600 text-white">
                                {pendingCount}
                            </span>
                        )}
                    </h1>
                    <p className="text-slate-500 mt-1">
                        Pending critical values requiring clinician notification and acknowledgment.
                    </p>
                </div>
                <button
                    onClick={loadNotifications}
                    className="btn-secondary text-sm"
                    disabled={loading}
                >
                    {loading ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>

            {message && (
                <div className={`p-3 rounded text-sm flex items-center justify-between ${message.startsWith('Error') ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
                    <span>{message}</span>
                    <button onClick={() => setMessage('')} className="ml-3 underline text-xs">Dismiss</button>
                </div>
            )}

            {/* Urgent banner */}
            {pendingCount > 0 && (
                <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
                    <div>
                        <p className="font-semibold text-red-800">
                            {pendingCount} critical value{pendingCount !== 1 ? 's' : ''} pending acknowledgment
                        </p>
                        <p className="text-sm text-red-700 mt-0.5">
                            Each notification must be acknowledged after notifying the responsible clinician per laboratory policy.
                        </p>
                    </div>
                </div>
            )}

            {/* Notifications table */}
            <Card>
                {loading ? (
                    <div className="py-12 text-center text-slate-400">Loading notifications...</div>
                ) : notifications.length === 0 ? (
                    <div className="py-12 text-center">
                        <CheckCircle className="w-10 h-10 text-green-400 mx-auto mb-3" />
                        <p className="text-slate-500 font-medium">No pending critical value notifications.</p>
                        <p className="text-slate-400 text-sm mt-1">All critical values have been acknowledged.</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200 text-left">
                                    <th className="pb-3 pr-4 font-semibold text-slate-600">Patient</th>
                                    <th className="pb-3 pr-4 font-semibold text-slate-600">MRN</th>
                                    <th className="pb-3 pr-4 font-semibold text-slate-600">Accession #</th>
                                    <th className="pb-3 pr-4 font-semibold text-slate-600">Test</th>
                                    <th className="pb-3 pr-4 font-semibold text-slate-600">Value</th>
                                    <th className="pb-3 pr-4 font-semibold text-slate-600">Type</th>
                                    <th className="pb-3 pr-4 font-semibold text-slate-600">Time</th>
                                    <th className="pb-3 font-semibold text-slate-600">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {notifications.map(notif => (
                                    <tr key={notif.id} className="hover:bg-red-50/40 transition-colors">
                                        <td className="py-3 pr-4 font-medium text-slate-900">
                                            {notif.patientName || '—'}
                                        </td>
                                        <td className="py-3 pr-4 font-mono text-slate-600 text-xs">
                                            {notif.mrn || '—'}
                                        </td>
                                        <td className="py-3 pr-4 font-mono text-slate-600 text-xs">
                                            {notif.accessionNumber || '—'}
                                        </td>
                                        <td className="py-3 pr-4">
                                            <span className="font-mono font-semibold">{notif.testCode}</span>
                                        </td>
                                        <td className="py-3 pr-4">
                                            <span className="font-bold text-red-700 text-base">{notif.value}</span>
                                            <span className="text-xs text-slate-400 ml-1">(critical: {notif.threshold})</span>
                                        </td>
                                        <td className="py-3 pr-4">
                                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${notif.criticalType === 'HIGH' ? 'bg-red-100 text-red-700 border border-red-200' : 'bg-blue-100 text-blue-700 border border-blue-200'}`}>
                                                {notif.criticalType}
                                            </span>
                                        </td>
                                        <td className="py-3 pr-4 text-slate-500 text-xs whitespace-nowrap">
                                            {formatTime(notif.createdAt)}
                                        </td>
                                        <td className="py-3">
                                            <button
                                                onClick={() => openAck(notif.id)}
                                                className="px-3 py-1.5 text-xs font-semibold bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
                                            >
                                                Acknowledge
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </Card>

            {/* Acknowledgment Modal */}
            {ackingId && (() => {
                const notif = notifications.find(n => n.id === ackingId);
                if (!notif) return null;
                return (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                        <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4">
                            {/* Modal Header */}
                            <div className="flex items-start justify-between p-6 border-b border-slate-200">
                                <div>
                                    <h2 className="text-lg font-bold text-slate-900">
                                        Acknowledge Critical Value
                                    </h2>
                                    <p className="text-sm text-slate-500 mt-1">
                                        {notif.testCode} = <strong className="text-red-700">{notif.value}</strong>
                                        {' '}({notif.criticalType})
                                        {notif.patientName && <> &mdash; {notif.patientName}</>}
                                    </p>
                                </div>
                                <button onClick={closeAck} className="text-slate-400 hover:text-slate-600 p-1 rounded">
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            {/* Modal Body */}
                            <form onSubmit={handleAckSubmit} className="p-6 space-y-4">
                                <div>
                                    <label className="label">Notified Clinician *</label>
                                    <input
                                        type="text"
                                        className="input-field"
                                        placeholder="e.g. Dr. Smith"
                                        value={ackForm.notifiedClinician}
                                        onChange={e => setAckForm(prev => ({ ...prev, notifiedClinician: e.target.value }))}
                                        required
                                        autoFocus
                                    />
                                </div>

                                <div>
                                    <label className="label">Notification Method *</label>
                                    <select
                                        className="input-field"
                                        value={ackForm.notificationMethod}
                                        onChange={e => setAckForm(prev => ({ ...prev, notificationMethod: e.target.value as AckForm['notificationMethod'] }))}
                                    >
                                        <option value="phone">Phone</option>
                                        <option value="fax">Fax</option>
                                        <option value="in-person">In-Person</option>
                                    </select>
                                </div>

                                <div>
                                    <label className="label">Notes</label>
                                    <textarea
                                        className="input-field min-h-[80px] resize-y"
                                        placeholder="Optional notes (e.g. time of call, read-back performed...)"
                                        value={ackForm.notes}
                                        onChange={e => setAckForm(prev => ({ ...prev, notes: e.target.value }))}
                                    />
                                </div>

                                <div className="flex gap-3 pt-2">
                                    <button
                                        type="submit"
                                        disabled={submitting}
                                        className="flex-1 px-4 py-2 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 transition-colors disabled:opacity-60"
                                    >
                                        {submitting ? 'Submitting...' : 'Confirm Acknowledgment'}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={closeAck}
                                        className="px-4 py-2 bg-slate-100 text-slate-700 font-semibold rounded-lg hover:bg-slate-200 transition-colors"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                );
            })()}
        </div>
    );
}
