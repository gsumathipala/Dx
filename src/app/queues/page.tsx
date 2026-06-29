"use client";

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Card } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/Badge';
import Link from 'next/link';
import { formatDateTime } from '@/lib/utils';

export default function MyQueuesPage() {
    const { user } = useAuth();
    const [queues, setQueues] = useState<any[]>([]);
    const [orders, setOrders] = useState<any[]>([]);
    const [patientMap, setPatientMap] = useState<Record<string, string>>({});
    const [selectedQueueId, setSelectedQueueId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const [qRes, oRes, pRes] = await Promise.all([
                    fetch('/api/queues'),
                    fetch('/api/orders'),
                    fetch('/api/patients')
                ]);

                if (!qRes.ok) {
                    setQueues([]);
                } else {
                    const qData = await qRes.json();
                    if (Array.isArray(qData)) {
                        setQueues(qData);
                        if (qData.length > 0) setSelectedQueueId(qData[0].id);
                    } else {
                        setQueues([]);
                    }
                }

                const oData = oRes.ok ? await oRes.json() : [];
                setOrders(Array.isArray(oData) ? oData : []);

                if (pRes.ok) {
                    const pData = await pRes.json();
                    if (Array.isArray(pData)) {
                        const map: Record<string, string> = {};
                        for (const p of pData) map[p.id] = `${p.lastName}, ${p.firstName}`;
                        setPatientMap(map);
                    }
                }
            } catch (e) {
                console.error("Failed to load queues/orders", e);
                setQueues([]);
                setOrders([]);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, []);

    // Filter orders for selected queue
    const queueOrders = orders.filter(o => o.queueId === selectedQueueId);
    const selectedQueue = queues.find(q => q.id === selectedQueueId);

    if (loading) return <div className="p-8 text-slate-500">Loading Work Queues...</div>;

    if (queues.length === 0) {
        return (
            <div className="p-12 text-center">
                <h2 className="text-xl font-bold text-slate-800 mb-2">No Active Queues</h2>
                <p className="text-slate-500">You are not assigned to any workflow queues currently.</p>
            </div>
        );
    }

    return (
        <div className="flex h-[calc(100vh-100px)] gap-6 p-6">
            {/* Sidebar List of Queues */}
            <div className="w-64 flex flex-col gap-4">
                <h2 className="font-bold text-lg text-slate-800 px-2">My Work Queues</h2>
                <div className="flex-1 overflow-y-auto space-y-2">
                    {queues.map(q => {
                        const count = orders.filter(o => o.queueId === q.id).length;
                        return (
                            <button
                                key={q.id}
                                onClick={() => setSelectedQueueId(q.id)}
                                className={`w-full text-left p-4 rounded-lg border transition-all ${selectedQueueId === q.id
                                    ? 'bg-blue-50 border-blue-500 shadow-sm'
                                    : 'bg-white border-slate-200 hover:bg-slate-50 hover:border-blue-300'
                                    }`}
                            >
                                <div className="flex justify-between items-center mb-1">
                                    <span className={`font-bold ${selectedQueueId === q.id ? 'text-blue-800' : 'text-slate-700'}`}>
                                        {q.name}
                                    </span>
                                    {count > 0 && (
                                        <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2 py-0.5 rounded-full">
                                            {count}
                                        </span>
                                    )}
                                </div>
                                <p className="text-xs text-slate-500 truncate">{q.description || 'No description'}</p>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col">
                <Card className="h-full flex flex-col p-0 overflow-hidden">
                    <div className="p-6 border-b bg-slate-50 flex justify-between items-center">
                        <div>
                            <h1 className="text-2xl font-bold text-slate-900">{selectedQueue?.name}</h1>
                            <p className="text-slate-500">{selectedQueue?.description}</p>
                        </div>
                        <div className="text-sm text-slate-500">
                            {queueOrders.length} items pending
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto p-0">
                        {queueOrders.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-slate-400">
                                <div className="text-4xl mb-4">✨</div>
                                <p>This queue is empty. Good job!</p>
                            </div>
                        ) : (
                            <table className="w-full text-left">
                                <thead className="bg-slate-100 border-b sticky top-0 z-10">
                                    <tr>
                                        <th className="p-4 font-semibold text-slate-700">Accession</th>
                                        <th className="p-4 font-semibold text-slate-700">Patient</th>
                                        <th className="p-4 font-semibold text-slate-700">Priority</th>
                                        <th className="p-4 font-semibold text-slate-700">Status</th>
                                        <th className="p-4 font-semibold text-slate-700">Created</th>
                                        <th className="p-4 font-semibold text-slate-700 text-right">Action</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {queueOrders.map(order => (
                                        <tr key={order.id} className="hover:bg-slate-50 transition-colors group">
                                            <td className="p-4 font-medium text-slate-900">{order.accessionNumber}</td>
                                            <td className="p-4 text-slate-600">{patientMap[order.patientId] || order.patientId}</td>
                                            <td className="p-4">
                                                <span className={`font-bold ${order.priority === 'STAT' ? 'text-red-600' : 'text-slate-600'}`}>
                                                    {order.priority}
                                                </span>
                                            </td>
                                            <td className="p-4"><StatusBadge status={order.status} /></td>
                                            <td className="p-4 text-slate-500 text-sm">{formatDateTime(order.timestamp)}</td>
                                            <td className="p-4 text-right">
                                                <Link
                                                    href={`/results?orderId=${order.id}`}
                                                    className="inline-flex items-center px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 transition-colors opacity-0 group-hover:opacity-100"
                                                >
                                                    Process Order →
                                                </Link>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </Card>
            </div>
        </div>
    );
}
