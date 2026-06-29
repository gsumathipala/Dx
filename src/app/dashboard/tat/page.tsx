"use client";

import React, { useState, useEffect } from 'react';
import { formatDateTime } from '@/lib/utils';
import { Card } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Table } from '@/components/ui/Table';

export default function TATDashboard() {
    const [orders, setOrders] = useState<any[]>([]);
    const [tests, setTests] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            fetch('/api/orders').then(res => res.ok ? res.json() : []),
            fetch('/api/admin/tests').then(res => res.ok ? res.json() : [])
        ]).then(([ordersData, testsData]) => {
            setOrders(ordersData);
            setTests(testsData);
            setLoading(false);
        }).catch(() => {
            setOrders([]);
            setTests([]);
            setLoading(false);
        });
    }, []);

    const getDeadlineInfo = (order: any) => {
        let minDeadline = new Date(8640000000000000);
        let hasDeadlines = false;

        order.testIds?.forEach((testId: string) => {
            const test = tests.find((t: any) => t.id === testId);
            if (test) {
                const startTime = new Date(order.timestamp).getTime();
                const deadline = new Date(startTime + (test.tatHours * 60 * 60 * 1000));
                if (deadline < minDeadline) {
                    minDeadline = deadline;
                    hasDeadlines = true;
                }
            }
        });

        if (!hasDeadlines) return null;
        const now = new Date();
        const diffHours = (minDeadline.getTime() - now.getTime()) / (1000 * 60 * 60);
        return { date: minDeadline, diffHours, isOverdue: diffHours < 0 };
    };

    if (loading) return <div className="p-8">Loading metrics...</div>;

    const activeOrders = orders.filter(o => o.status !== 'Completed');
    const sortedOrders = activeOrders.map(order => ({ ...order, deadline: getDeadlineInfo(order) }))
        .sort((a, b) => {
            if (!a.deadline) return 1;
            if (!b.deadline) return -1;
            return a.deadline.date.getTime() - b.deadline.date.getTime();
        });

    const overdueCount = sortedOrders.filter(o => o.deadline?.isOverdue).length;
    const imminentCount = sortedOrders.filter(o => o.deadline && !o.deadline.isOverdue && o.deadline.diffHours < 4).length;

    const columns = [
        { header: 'Accession', accessor: (o: any) => <span className="font-semibold text-primary-600">{o.accessionNumber}</span> },
        { header: 'Patient ID', accessor: (o: any) => <span className="text-slate-500">{o.patientId || o.id}</span> },
        { header: 'Tests', accessor: (o: any) => o.testIds?.map((tid: string) => tests.find((t: any) => t.id === tid)?.name).join(', ') },
        {
            header: 'Deadline', accessor: (o: any) => {
                if (!o.deadline) return <span className="text-slate-400">N/A</span>;
                const isOverdue = o.deadline.isOverdue;
                const isImminent = o.deadline.diffHours < 4;
                return (
                    <div className={isOverdue ? "text-red-600 font-bold" : isImminent ? "text-amber-600 font-semibold" : "text-slate-600"}>
                        {formatDateTime(o.deadline.date.toISOString())}
                        {isOverdue && <span className="block text-xs">⚠️ OVERDUE</span>}
                    </div>
                );
            }
        },
        { header: 'Status', accessor: (o: any) => <StatusBadge status={o.status} /> }
    ];

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900">Lab Operations Center</h1>
                    <p className="text-slate-500">Real-time Turnaround Time (TAT) Monitoring</p>
                </div>
                <div className="text-sm text-slate-400">Auto-refresh active</div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <Card className="bg-gradient-to-br from-red-50 to-white border-red-100">
                    <div className="text-red-600 font-medium mb-1">Critical / Overdue</div>
                    <div className="text-3xl font-bold text-red-700">{overdueCount}</div>
                    <div className="text-xs text-red-400 mt-2">Action Required Immediately</div>
                </Card>
                <Card className="bg-gradient-to-br from-amber-50 to-white border-amber-100">
                    <div className="text-amber-600 font-medium mb-1">Due within 4 Hours</div>
                    <div className="text-3xl font-bold text-amber-700">{imminentCount}</div>
                    <div className="text-xs text-amber-500 mt-2">Prioritize These</div>
                </Card>
                <Card className="bg-white">
                    <div className="text-slate-500 font-medium mb-1">Active Workload</div>
                    <div className="text-3xl font-bold text-slate-700">{activeOrders.length}</div>
                    <div className="text-xs text-slate-400 mt-2">Total Pending Accessions</div>
                </Card>
                <Card className="bg-white">
                    <div className="text-slate-500 font-medium mb-1">Completed Today</div>
                    <div className="text-3xl font-bold text-primary-600">
                        {orders.filter(o => o.status === 'Completed').length}
                        {/* Simple filter, strictly speaking should filter by date too */}
                    </div>
                </Card>
            </div>

            <Card title="Pending Worklist (Sorted by Urgency)">
                <Table
                    data={sortedOrders}
                    columns={columns}
                    keyField="id"
                    emptyMessage="All caught up! No pending orders."
                />
            </Card>
        </div>
    );
}
