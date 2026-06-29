'use client';

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, LineChart, Line, Legend
} from 'recharts';
import { TrendingUp, CheckCircle, Clock, AlertTriangle, Zap } from 'lucide-react';

interface KpiData {
    volumeByDay: { date: string; count: number }[];
    volumeByDepartment: { department: string; count: number }[];
    tatCompliance: { overall: number; byDepartment: { dept: string; compliance: number }[] };
    rejectionRate: number;
    completionRate: number;
    avgTatHours: number;
    statOrders: number;
    criticalResults: number;
    topTests: { testCode: string; count: number }[];
}

const PIE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316', '#84cc16'];

const DAYS_OPTIONS = [
    { label: '7 days', value: 7 },
    { label: '30 days', value: 30 },
    { label: '90 days', value: 90 },
    { label: '1 year', value: 365 },
];

function StatCard({ label, value, sub, icon: Icon, color }: {
    label: string; value: string | number; sub?: string;
    icon: React.ElementType; color: string;
}) {
    return (
        <div className={`bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex items-start gap-4`}>
            <div className={`p-2.5 rounded-lg ${color}`}>
                <Icon size={20} className="text-white" />
            </div>
            <div>
                <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">{label}</p>
                <p className="text-2xl font-bold text-slate-900 mt-0.5">{value}</p>
                {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
            </div>
        </div>
    );
}

export default function KpiDashboardPage() {
    const [days, setDays] = useState(30);
    const [data, setData] = useState<KpiData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        fetch(`/api/kpi?days=${days}`)
            .then((r) => r.json())
            .then((json) => setData(json))
            .catch(console.error)
            .finally(() => setLoading(false));
    }, [days]);

    return (
        <div className="min-h-screen bg-slate-50 p-6">
            <div className="max-w-7xl mx-auto space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">KPI Management Dashboard</h1>
                        <p className="text-slate-500 text-sm mt-1">Laboratory performance metrics and analytics</p>
                    </div>
                    <div className="flex gap-1 bg-white rounded-lg border border-slate-200 p-1 shadow-sm">
                        {DAYS_OPTIONS.map((opt) => (
                            <button
                                key={opt.value}
                                onClick={() => setDays(opt.value)}
                                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                                    days === opt.value
                                        ? 'bg-blue-600 text-white'
                                        : 'text-slate-600 hover:bg-slate-100'
                                }`}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </div>

                {loading ? (
                    <div className="text-center py-16 text-slate-400">Loading KPI data...</div>
                ) : data ? (
                    <>
                        {/* Stats Row */}
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                            <StatCard
                                label="Total Orders"
                                value={data.volumeByDay.reduce((s, d) => s + d.count, 0)}
                                sub={`Last ${days} days`}
                                icon={TrendingUp}
                                color="bg-blue-500"
                            />
                            <StatCard
                                label="Completion Rate"
                                value={`${data.completionRate}%`}
                                icon={CheckCircle}
                                color="bg-emerald-500"
                            />
                            <StatCard
                                label="Avg TAT"
                                value={`${data.avgTatHours}h`}
                                sub={`TAT compliance: ${data.tatCompliance.overall}%`}
                                icon={Clock}
                                color="bg-amber-500"
                            />
                            <StatCard
                                label="STAT Orders"
                                value={data.statOrders}
                                icon={Zap}
                                color="bg-purple-500"
                            />
                            <StatCard
                                label="Critical Results"
                                value={data.criticalResults}
                                sub={`Rejection: ${data.rejectionRate}%`}
                                icon={AlertTriangle}
                                color="bg-red-500"
                            />
                        </div>

                        {/* Charts Row 1 */}
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                            {/* Daily Volume */}
                            <div className="lg:col-span-2">
                                <Card title="Daily Order Volume">
                                    <div className="h-64">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={data.volumeByDay} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                                <XAxis
                                                    dataKey="date"
                                                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                                                    tickFormatter={(v) => v.substring(5)}
                                                />
                                                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                                                <Tooltip
                                                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                                                    labelFormatter={(v) => `Date: ${v}`}
                                                />
                                                <Bar dataKey="count" fill="#3b82f6" radius={[3, 3, 0, 0]} name="Orders" />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                </Card>
                            </div>

                            {/* Orders by Department Pie */}
                            <div>
                                <Card title="Orders by Department">
                                    <div className="h-64">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={data.volumeByDepartment}
                                                    dataKey="count"
                                                    nameKey="department"
                                                    cx="50%"
                                                    cy="50%"
                                                    outerRadius={80}
                                                    label={false}
                                                    labelLine={false}
                                                >
                                                    {data.volumeByDepartment.map((_, i) => (
                                                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                                                    ))}
                                                </Pie>
                                                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </Card>
                            </div>
                        </div>

                        {/* Charts Row 2 */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            {/* TAT Compliance by Dept */}
                            <Card title="TAT Compliance by Department">
                                {data.tatCompliance.byDepartment.length === 0 ? (
                                    <div className="text-slate-400 text-sm py-8 text-center">No TAT data available.</div>
                                ) : (
                                    <div className="h-56">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart
                                                data={data.tatCompliance.byDepartment}
                                                layout="vertical"
                                                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                                            >
                                                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} unit="%" />
                                                <YAxis dataKey="dept" type="category" tick={{ fontSize: 10, fill: '#94a3b8' }} width={80} />
                                                <Tooltip
                                                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                                                    formatter={(v) => [`${v}%`, 'Compliance']}
                                                />
                                                <Bar
                                                    dataKey="compliance"
                                                    radius={[0, 3, 3, 0]}
                                                    name="Compliance %"
                                                    fill="#10b981"
                                                />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                )}
                            </Card>

                            {/* Top Tests Table */}
                            <Card title="Top Ordered Tests">
                                {data.topTests.length === 0 ? (
                                    <div className="text-slate-400 text-sm py-8 text-center">No test data available.</div>
                                ) : (
                                    <div className="overflow-hidden">
                                        <table className="w-full text-sm">
                                            <thead>
                                                <tr className="border-b border-slate-100">
                                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase">#</th>
                                                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase">Test Code</th>
                                                    <th className="text-right py-2 px-3 text-xs font-semibold text-slate-500 uppercase">Orders</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {data.topTests.map((t, i) => (
                                                    <tr key={t.testCode} className="border-b border-slate-50 hover:bg-slate-50">
                                                        <td className="py-2 px-3 text-slate-400 text-xs">{i + 1}</td>
                                                        <td className="py-2 px-3 font-mono font-medium text-slate-800">{t.testCode}</td>
                                                        <td className="py-2 px-3 text-right">
                                                            <span className="bg-blue-100 text-blue-700 text-xs font-semibold px-2 py-0.5 rounded-full">
                                                                {t.count}
                                                            </span>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </Card>
                        </div>
                    </>
                ) : (
                    <div className="text-center py-16 text-slate-400">Failed to load KPI data.</div>
                )}
            </div>
        </div>
    );
}
