"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';

export default function AnalyticsPage() {
    const [stats, setStats] = useState<any>(null);

    useEffect(() => {
        fetch('/api/analytics')
            .then(r => r.ok ? r.json() : { pending: 0, completed: 0, avgTat: 0, deptCounts: {} })
            .then(setStats)
            .catch(() => setStats({ pending: 0, completed: 0, avgTat: 0, deptCounts: {} }));
    }, []);

    if (!stats) return <div className="p-8">Loading Command Centre...</div>;

    const maxVol = Math.max(...Object.values(stats.deptCounts as Record<string, number>));

    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">HIVE Command Centre</h1>

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="bg-blue-600 text-white border-none shadow-xl">
                    <h3 className="font-bold text-blue-100 opacity-75">Pending Orders</h3>
                    <p className="text-6xl font-bold mt-2">{stats.pending}</p>
                    <p className="text-sm mt-2 opacity-75">Real-time Backlog</p>
                </Card>

                <Card className="bg-slate-800 text-white border-none shadow-xl">
                    <h3 className="font-bold text-slate-300 opacity-75">Avg Turnaround Time</h3>
                    <p className="text-6xl font-bold mt-2">{stats.avgTat}<span className="text-2xl ml-2 font-normal text-slate-400">min</span></p>
                    <p className="text-sm mt-2 opacity-75">Target: 60 min</p>
                </Card>

                <Card className="bg-purple-600 text-white border-none shadow-xl">
                    <h3 className="font-bold text-purple-100 opacity-75">Completed (Today)</h3>
                    <p className="text-6xl font-bold mt-2">{stats.completed}</p>
                    <p className="text-sm mt-2 opacity-75">Throughput Volume</p>
                </Card>
            </div>

            {/* Visuals */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card title="Department Load Balance">
                    <div className="space-y-4 pt-4">
                        {Object.entries(stats.deptCounts).map(([dept, count]: any) => (
                            <div key={dept}>
                                <div className="flex justify-between mb-1">
                                    <span className="font-bold text-slate-700">{dept}</span>
                                    <span className="font-mono">{count} tests</span>
                                </div>
                                <div className="h-4 bg-slate-100 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-blue-500 transition-all duration-1000"
                                        style={{ width: `${(count / (maxVol || 1)) * 100}%` }}
                                    ></div>
                                </div>
                            </div>
                        ))}
                    </div>
                </Card>

                <Card title="Operational Alerts">
                    <div className="space-y-2">
                        {stats.pending > 10 && (
                            <div className="p-4 bg-red-100 text-red-800 rounded flex items-center gap-3 animate-pulse">
                                <span className="text-2xl">⚠️</span>
                                <div>
                                    <p className="font-bold">High Backlog Alert</p>
                                    <p className="text-sm">Pending volume exceeds threshold (10). Allocation required.</p>
                                </div>
                            </div>
                        )}
                        {stats.avgTat > 60 && (
                            <div className="p-4 bg-amber-100 text-amber-800 rounded flex items-center gap-3">
                                <span className="text-2xl">⏱️</span>
                                <div>
                                    <p className="font-bold">TAT Warning</p>
                                    <p className="text-sm">Average TAT is slipping ({stats.avgTat} min).</p>
                                </div>
                            </div>
                        )}
                        {stats.pending <= 10 && stats.avgTat <= 60 && (
                            <div className="p-4 bg-green-100 text-green-800 rounded flex items-center gap-3">
                                <span className="text-2xl">✅</span>
                                <div>
                                    <p className="font-bold">Operations Nominal</p>
                                    <p className="text-sm">Lab performing within key metrics.</p>
                                </div>
                            </div>
                        )}
                    </div>
                </Card>

                {/* Surveillance / Epidemiology Module */}
                <div className="lg:col-span-2">
                    <Card title="Epidemiology & Surveillance Export">
                        <div className="bg-slate-50 p-4 rounded border border-slate-200">
                            <p className="text-sm text-slate-500 mb-4">
                                Generate de-identified datasets for Ministry of Health reporting and epidemiological tracking.
                            </p>
                            <form
                                className="flex flex-wrap gap-4 items-end"
                                onSubmit={(e) => {
                                    e.preventDefault();
                                    const form = e.target as HTMLFormElement;
                                    const start = (form.elements.namedItem('startDate') as HTMLInputElement).value;
                                    const end = (form.elements.namedItem('endDate') as HTMLInputElement).value;
                                    const disease = (form.elements.namedItem('disease') as HTMLInputElement).value;
                                    window.open(`/api/analytics/export?startDate=${start}&endDate=${end}&disease=${disease}`, '_blank');
                                }}
                            >
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-1">Start Date</label>
                                    <input name="startDate" type="date" className="input-field p-2 border rounded" required />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-1">End Date</label>
                                    <input name="endDate" type="date" className="input-field p-2 border rounded" required />
                                </div>
                                <div className="flex-1 min-w-[200px]">
                                    <label className="block text-xs font-bold text-slate-700 mb-1">Pathogen / Condition</label>
                                    <select name="disease" className="input-field w-full p-2 border rounded">
                                        <option value="All">All Reportable Conditions</option>
                                        <option value="HIV">HIV / Retroviral</option>
                                        <option value="COVID">COVID-19 / SARS-CoV-2</option>
                                        <option value="Malaria">Malaria</option>
                                        <option value="TB">Tuberculosis</option>
                                    </select>
                                </div>
                                <button type="submit" className="bg-slate-800 text-white px-4 py-2 rounded font-bold hover:bg-slate-700">
                                    ⬇️ Export CSV
                                </button>
                            </form>
                        </div>
                    </Card>
                </div>
            </div>
        </div>
    );
}
