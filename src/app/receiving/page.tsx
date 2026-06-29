'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { FlaskConical, CheckCircle, XCircle, AlertTriangle, Clock, ChevronRight } from 'lucide-react';

type PendingOrder = {
    id: string;
    accessionNumber: string;
    patientName: string;
    specimenType: string;
    timestamp: string;
    priority: string;
    specimenId: string;
};

type ReceivedRecord = {
    id: string;
    accessionNumber: string;
    patientName: string;
    specimenType: string;
    receivedAt: string;
    receivedBy: string;
    condition: string;
    status: 'Accepted' | 'Rejected' | 'Recollection-Required';
    conditionNotes?: string;
    rejectionReason?: string;
    temperature?: string;
    volume?: number;
};

type ReceiveForm = {
    condition: 'Acceptable' | 'Marginal' | 'Rejected';
    conditionNotes: string;
    rejectionReason: string;
    temperature: string;
    volume: string;
};

const defaultForm: ReceiveForm = {
    condition: 'Acceptable',
    conditionNotes: '',
    rejectionReason: '',
    temperature: '',
    volume: '',
};

function StatusBadge({ status }: { status: string }) {
    const map: Record<string, string> = {
        'Accepted': 'bg-green-100 text-green-800',
        'Rejected': 'bg-red-100 text-red-800',
        'Recollection-Required': 'bg-amber-100 text-amber-800',
    };
    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${map[status] || 'bg-slate-100 text-slate-700'}`}>
            {status}
        </span>
    );
}

function PriorityBadge({ priority }: { priority: string }) {
    const map: Record<string, string> = {
        'STAT': 'bg-red-100 text-red-700',
        'Urgent': 'bg-orange-100 text-orange-700',
        'Routine': 'bg-slate-100 text-slate-600',
    };
    return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${map[priority] || 'bg-slate-100 text-slate-600'}`}>
            {priority}
        </span>
    );
}

export default function ReceivingPage() {
    const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>([]);
    const [receivedToday, setReceivedToday] = useState<ReceivedRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedOrder, setSelectedOrder] = useState<PendingOrder | null>(null);
    const [form, setForm] = useState<ReceiveForm>(defaultForm);
    const [submitting, setSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState('');

    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            // Fetch all orders and specimens to find pending
            const [ordersRes, specimensRes, receivingRes] = await Promise.all([
                fetch('/api/orders'),
                fetch('/api/specimens'),
                fetch('/api/receiving'),
            ]);

            const ordersData = ordersRes.ok ? await ordersRes.json() : [];
            const specimensData = specimensRes.ok ? await specimensRes.json() : [];
            const receivingData = receivingRes.ok ? await receivingRes.json() : [];

            const receivedSpecimenIds = new Set(receivingData.map((r: ReceivedRecord & { specimenId: string }) => r.specimenId));

            // Build pending: specimens with no receiving record, joined with orders + patients
            const pending: PendingOrder[] = [];
            for (const specimen of specimensData) {
                if (receivedSpecimenIds.has(specimen.id)) continue;
                const order = ordersData.find((o: PendingOrder) => o.id === specimen.orderId);
                if (!order) continue;
                pending.push({
                    id: order.id,
                    accessionNumber: order.accessionNumber,
                    patientName: order.patientName || '',
                    specimenType: specimen.type,
                    timestamp: order.timestamp,
                    priority: order.priority || 'Routine',
                    specimenId: specimen.id,
                });
            }

            setPendingOrders(pending);

            // Received today
            const today = new Date().toISOString().split('T')[0];
            const todayRecords = receivingData.filter((r: ReceivedRecord & { receivedAt: string }) =>
                r.receivedAt?.startsWith(today)
            );
            setReceivedToday(todayRecords);
        } catch (err) {
            console.error('Error loading receiving data:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const handleSelectOrder = (order: PendingOrder) => {
        setSelectedOrder(order);
        setForm(defaultForm);
        setSubmitError('');
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedOrder) return;
        setSubmitting(true);
        setSubmitError('');

        try {
            const res = await fetch('/api/receiving', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    specimenId: selectedOrder.specimenId,
                    orderId: selectedOrder.id,
                    condition: form.condition,
                    conditionNotes: form.conditionNotes || undefined,
                    rejectionReason: form.rejectionReason || undefined,
                    temperature: form.temperature || undefined,
                    volume: form.volume ? parseFloat(form.volume) : undefined,
                }),
            });

            if (!res.ok) {
                const err = await res.json();
                setSubmitError(err.error || 'Failed to submit');
                return;
            }

            setSelectedOrder(null);
            setForm(defaultForm);
            await loadData();
        } catch (err) {
            setSubmitError('Network error. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    const formatTime = (iso: string) => {
        if (!iso) return '—';
        return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    };

    const showRejectionFields = form.condition === 'Rejected' || form.condition === 'Marginal';

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto">
            <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-blue-50 rounded-lg">
                    <FlaskConical className="h-6 w-6 text-blue-600" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Specimen Receiving</h1>
                    <p className="text-sm text-slate-500">Process incoming specimens and record condition</p>
                </div>
            </div>

            {/* Pending Reception */}
            <Card title="Pending Reception" description="Specimens awaiting reception processing">
                {loading ? (
                    <div className="flex items-center justify-center py-12 text-slate-400">
                        <Clock className="h-5 w-5 animate-spin mr-2" /> Loading...
                    </div>
                ) : pendingOrders.length === 0 ? (
                    <div className="flex items-center justify-center py-12 text-slate-400">
                        <CheckCircle className="h-5 w-5 mr-2 text-green-400" /> All specimens have been received
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100">
                        {pendingOrders.map(order => (
                            <div key={order.specimenId}>
                                <button
                                    onClick={() => handleSelectOrder(order)}
                                    className={`w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors flex items-center gap-4 ${selectedOrder?.specimenId === order.specimenId ? 'bg-blue-50 border-l-2 border-blue-500' : ''}`}
                                >
                                    <FlaskConical className="h-4 w-4 text-slate-400 flex-shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span className="font-mono text-sm font-semibold text-slate-800">{order.accessionNumber}</span>
                                            <PriorityBadge priority={order.priority} />
                                        </div>
                                        <div className="text-sm text-slate-600 mt-0.5">
                                            {order.patientName || <span className="text-slate-400 italic">Unknown patient</span>}
                                            <span className="text-slate-400 mx-1.5">·</span>
                                            <span className="text-slate-500">{order.specimenType}</span>
                                        </div>
                                    </div>
                                    <div className="text-right text-xs text-slate-400 flex-shrink-0">
                                        <div>{formatTime(order.timestamp)}</div>
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-slate-300 flex-shrink-0" />
                                </button>

                                {/* Inline receive form */}
                                {selectedOrder?.specimenId === order.specimenId && (
                                    <div className="mx-4 mb-4 p-4 bg-blue-50 border border-blue-100 rounded-lg">
                                        <h3 className="text-sm font-semibold text-slate-800 mb-3">
                                            Receive Specimen — {order.accessionNumber}
                                        </h3>
                                        <form onSubmit={handleSubmit} className="space-y-3">
                                            <div>
                                                <label className="block text-xs font-medium text-slate-700 mb-1">Condition *</label>
                                                <select
                                                    value={form.condition}
                                                    onChange={e => setForm(f => ({ ...f, condition: e.target.value as ReceiveForm['condition'] }))}
                                                    className="w-full sm:w-48 border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                                                    required
                                                >
                                                    <option value="Acceptable">Acceptable</option>
                                                    <option value="Marginal">Marginal</option>
                                                    <option value="Rejected">Rejected</option>
                                                </select>
                                            </div>

                                            {showRejectionFields && (
                                                <div>
                                                    <label className="block text-xs font-medium text-slate-700 mb-1">
                                                        Rejection / Issue Reason
                                                    </label>
                                                    <textarea
                                                        value={form.rejectionReason}
                                                        onChange={e => setForm(f => ({ ...f, rejectionReason: e.target.value }))}
                                                        className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white resize-none"
                                                        rows={2}
                                                        placeholder="Describe the rejection or issue reason..."
                                                    />
                                                </div>
                                            )}

                                            <div>
                                                <label className="block text-xs font-medium text-slate-700 mb-1">Condition Notes</label>
                                                <textarea
                                                    value={form.conditionNotes}
                                                    onChange={e => setForm(f => ({ ...f, conditionNotes: e.target.value }))}
                                                    className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white resize-none"
                                                    rows={2}
                                                    placeholder="Additional notes about specimen condition..."
                                                />
                                            </div>

                                            <div className="flex gap-3">
                                                <div>
                                                    <label className="block text-xs font-medium text-slate-700 mb-1">Temperature on Arrival</label>
                                                    <input
                                                        type="text"
                                                        value={form.temperature}
                                                        onChange={e => setForm(f => ({ ...f, temperature: e.target.value }))}
                                                        className="w-36 border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                                                        placeholder="e.g. 4°C"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-xs font-medium text-slate-700 mb-1">Volume Received (mL)</label>
                                                    <input
                                                        type="number"
                                                        value={form.volume}
                                                        onChange={e => setForm(f => ({ ...f, volume: e.target.value }))}
                                                        className="w-32 border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                                                        placeholder="0.0"
                                                        min="0"
                                                        step="0.1"
                                                    />
                                                </div>
                                            </div>

                                            {submitError && (
                                                <div className="flex items-center gap-2 text-red-600 text-sm">
                                                    <AlertTriangle className="h-4 w-4" /> {submitError}
                                                </div>
                                            )}

                                            <div className="flex gap-2 pt-1">
                                                <button
                                                    type="submit"
                                                    disabled={submitting}
                                                    className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                                >
                                                    {submitting ? 'Submitting...' : 'Submit Reception'}
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setSelectedOrder(null)}
                                                    className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-md text-sm font-medium hover:bg-slate-50 transition-colors"
                                                >
                                                    Cancel
                                                </button>
                                            </div>
                                        </form>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </Card>

            {/* Received Today */}
            <Card title="Received Today" description="Specimens processed today">
                {loading ? (
                    <div className="flex items-center justify-center py-8 text-slate-400">
                        <Clock className="h-4 w-4 animate-spin mr-2" /> Loading...
                    </div>
                ) : receivedToday.length === 0 ? (
                    <div className="text-center py-8 text-slate-400 text-sm">No specimens received today</div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200">
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Accession</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Patient</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Specimen</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Condition</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Received By</th>
                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Time</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {receivedToday.map(rec => (
                                    <tr key={rec.id} className="hover:bg-slate-50">
                                        <td className="py-2 px-3 font-mono text-xs font-semibold text-slate-800">{rec.accessionNumber}</td>
                                        <td className="py-2 px-3 text-slate-700">{rec.patientName || '—'}</td>
                                        <td className="py-2 px-3 text-slate-600">{rec.specimenType || '—'}</td>
                                        <td className="py-2 px-3 text-slate-600">{rec.condition}</td>
                                        <td className="py-2 px-3"><StatusBadge status={rec.status} /></td>
                                        <td className="py-2 px-3 text-slate-600">{rec.receivedBy}</td>
                                        <td className="py-2 px-3 text-slate-500">{formatTime(rec.receivedAt)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </Card>
        </div>
    );
}
