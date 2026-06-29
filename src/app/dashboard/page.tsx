"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import Link from 'next/link';
import {
    Activity, Clock, CheckCircle, AlertCircle, TrendingUp,
    TestTube, Users, FileText, ArrowRight, ArrowLeft, Layers
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Table } from '@/components/ui/Table';

export default function DashboardPage() {
    const { user } = useAuth();
    const [stats, setStats] = useState({
        pending: 0,
        completed: 0,
        critical: 0,
        tat: '0h'
    });

    // View State
    const [view, setView] = useState<'MAIN' | 'PENDING' | 'COMPLETED' | 'CRITICAL' | 'TAT'>('MAIN');
    const [detailData, setDetailData] = useState<any[]>([]);
    const [loadingDetails, setLoadingDetails] = useState(false);
    const [selectedDept, setSelectedDept] = useState<string>('ALL');
    const [departments, setDepartments] = useState<string[]>([]);

    useEffect(() => {
        // Fetch active departments
        fetch('/api/departments')
            .then(res => res.json())
            .then(data => {
                if (Array.isArray(data)) {
                    setDepartments(['ALL', ...data]);
                }
            })
            .catch(err => console.error("Failed to load departments", err));

        if (user && user.role !== 'admin') {
            setSelectedDept(user.department || 'ALL');
        }
    }, [user]);

    const [alerts, setAlerts] = useState<any[]>([]);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const query = selectedDept && selectedDept !== 'ALL' ? `?department=${selectedDept}` : '';
                const res = await fetch(`/api/dashboard/stats${query}`);
                if (res.ok) {
                    try {
                        const data = await res.json();
                        setStats(data);
                    } catch (err) {
                        console.error("Invalid JSON from stats:", err);
                    }
                }
            } catch (e) {
                console.error("Failed to fetch stats connection error");
            }
        };
        const fetchAlerts = async () => {
            try {
                const res = await fetch('/api/alerts/active');
                if (res.ok) {
                    try {
                        const data = await res.json();
                        setAlerts(data);
                    } catch (err) {
                        console.error("Invalid JSON from alerts:", err);
                    }
                }
            } catch (e) {
                console.error("Failed to fetch alerts connection error");
            }
        };

        if (user) {
            fetchStats();
            fetchAlerts();
        }
    }, [selectedDept, user]);

    const openDetail = async (type: 'PENDING' | 'COMPLETED' | 'CRITICAL' | 'TAT') => {
        setLoadingDetails(true);
        setView(type);
        try {
            const query = selectedDept && selectedDept !== 'ALL' ? `&department=${selectedDept}` : '';
            const res = await fetch(`/api/dashboard/details?type=${type}${query}`);
            if (res.ok) {
                setDetailData(await res.json());
            }
        } finally {
            setLoadingDetails(false);
        }
    };

    const backToMain = () => {
        setView('MAIN');
        setDetailData([]);
    };

    // Columns Config
    const orderColumns = [
        { header: 'Order ID', accessor: (d: any) => d.id },
        { header: 'Patient', accessor: (d: any) => d.patientName },
        { header: 'Tests', accessor: (d: any) => d.tests },
        { header: 'Priority', accessor: (d: any) => <span className={d.priority === 'STAT' ? 'text-red-600 font-bold' : ''}>{d.priority}</span> },
        { header: 'Created', accessor: (d: any) => new Date(d.createdAt).toLocaleString() },
    ];

    const criticalColumns = [
        { header: 'Patient', accessor: (d: any) => d.patientName },
        { header: 'Test', accessor: (d: any) => d.testName },
        { header: 'Result', accessor: (d: any) => <span className="font-bold text-red-600">{d.value}</span> },
        { header: 'Flag', accessor: (d: any) => <span className="bg-red-100 text-red-800 px-2 rounded font-bold">{d.flag}</span> },
        { header: 'Time', accessor: (d: any) => new Date(d.timestamp).toLocaleString() },
    ];

    const tatColumns = [
        ...orderColumns,
        { header: 'Turnaround', accessor: (d: any) => <span className="font-mono font-bold">{d.tatHours} hrs</span> },
    ];

    if (view !== 'MAIN') {
        const titleMap = {
            PENDING: 'Pending Orders',
            COMPLETED: 'Completed Today',
            CRITICAL: 'Critical Results',
            TAT: 'Turnaround Time Analysis'
        };

        const colMap = {
            PENDING: orderColumns,
            COMPLETED: orderColumns,
            CRITICAL: criticalColumns,
            TAT: tatColumns
        };

        return (
            <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
                <div className="flex items-center gap-4 border-b pb-4">
                    <button onClick={backToMain} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
                        <ArrowLeft className="w-6 h-6 text-slate-600" />
                    </button>
                    <h1 className="text-2xl font-bold text-slate-900">{titleMap[view]}</h1>
                </div>

                <Card>
                    <Table
                        data={detailData}
                        columns={colMap[view]}
                        keyField="id"
                        emptyMessage={loadingDetails ? "Loading..." : "No records found."}
                    />
                </Card>
            </div>
        );
    }

    // MAIN DASHBOARD VIEW
    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex justify-between items-end border-b border-slate-200 pb-6">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Laboratory Dashboard</h1>
                    <p className="text-slate-500 mt-1">
                        Welcome back, <span className="font-semibold text-primary-600">{user?.name}</span>.
                        Here is today&apos;s overview.
                    </p>
                </div>
                <div className="flex items-center gap-4">
                    {user?.role === 'admin' && (
                        <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-slate-500">View:</span>
                            <select
                                value={selectedDept}
                                onChange={(e) => setSelectedDept(e.target.value)}
                                className="input-field py-1 px-3 text-sm min-w-[150px]"
                            >
                                {departments.map(d => <option key={d} value={d}>{d === 'ALL' ? 'All Departments' : d}</option>)}
                            </select>
                        </div>
                    )}
                    {(user?.role !== 'admin' && selectedDept !== 'ALL') && (
                        <div className="bg-slate-100 px-3 py-1 rounded-full text-sm font-bold text-slate-600">
                            {selectedDept} Dashboard
                        </div>
                    )}
                    <div className="text-sm text-slate-400 font-medium text-right">
                        {new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                    </div>
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div onClick={() => openDetail('PENDING')} className="cursor-pointer transition-transform hover:-translate-y-1">
                    <Card className="border-l-4 border-l-blue-500 shadow-sm hover:shadow-lg h-full">
                        <div className="flex justify-between items-start">
                            <div>
                                <p className="text-sm font-medium text-slate-500 uppercase tracking-wider">Pending Orders</p>
                                <h3 className="text-3xl font-bold text-slate-900 mt-2">{stats.pending}</h3>
                            </div>
                            <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
                                <Clock className="w-6 h-6" />
                            </div>
                        </div>
                    </Card>
                </div>

                <div onClick={() => openDetail('COMPLETED')} className="cursor-pointer transition-transform hover:-translate-y-1">
                    <Card className="border-l-4 border-l-green-500 shadow-sm hover:shadow-lg h-full">
                        <div className="flex justify-between items-start">
                            <div>
                                <p className="text-sm font-medium text-slate-500 uppercase tracking-wider">Completed Today</p>
                                <h3 className="text-3xl font-bold text-slate-900 mt-2">{stats.completed}</h3>
                            </div>
                            <div className="p-2 bg-green-50 rounded-lg text-green-600">
                                <CheckCircle className="w-6 h-6" />
                            </div>
                        </div>
                    </Card>
                </div>

                <div onClick={() => openDetail('CRITICAL')} className="cursor-pointer transition-transform hover:-translate-y-1">
                    <Card className="border-l-4 border-l-red-500 shadow-sm hover:shadow-lg h-full">
                        <div className="flex justify-between items-start">
                            <div>
                                <p className="text-sm font-medium text-text-slate-500 uppercase tracking-wider">Critical Results</p>
                                <h3 className="text-3xl font-bold text-red-600 mt-2">{stats.critical}</h3>
                            </div>
                            <div className="p-2 bg-red-50 rounded-lg text-red-600">
                                <AlertCircle className="w-6 h-6" />
                            </div>
                        </div>
                    </Card>
                </div>

                <div onClick={() => openDetail('TAT')} className="cursor-pointer transition-transform hover:-translate-y-1">
                    <Card className="border-l-4 border-l-purple-500 shadow-sm hover:shadow-lg h-full">
                        <div className="flex justify-between items-start">
                            <div>
                                <p className="text-sm font-medium text-slate-500 uppercase tracking-wider">Avg Turnaround</p>
                                <h3 className="text-3xl font-bold text-slate-900 mt-2">{stats.tat}</h3>
                            </div>
                            <div className="p-2 bg-purple-50 rounded-lg text-purple-600">
                                <TrendingUp className="w-6 h-6" />
                            </div>
                        </div>
                    </Card>
                </div>
            </div>

            {/* Main Workflow Areas */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-2 space-y-6">
                    <h2 className="text-xl font-bold text-slate-800">Quick Actions</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <Link href="/accessioning" className="group">
                            <Card className="h-full hover:border-primary-400 transition-colors p-6 flex flex-col items-center text-center cursor-pointer bg-slate-50 group-hover:bg-white">
                                <div className="w-12 h-12 rounded-full bg-primary-100 flex items-center justify-center text-primary-600 mb-4 group-hover:scale-110 transition-transform">
                                    <TestTube className="w-6 h-6" />
                                </div>
                                <h3 className="font-bold text-slate-900 mb-1">Accession Sample</h3>
                                <p className="text-sm text-slate-500">Register new patient orders and print labels.</p>
                            </Card>
                        </Link>

                        <Link href="/tracking" className="group">
                            <Card className="h-full hover:border-blue-400 transition-colors p-6 flex flex-col items-center text-center cursor-pointer bg-slate-50 group-hover:bg-white">
                                <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 mb-4 group-hover:scale-110 transition-transform">
                                    <Activity className="w-6 h-6" />
                                </div>
                                <h3 className="font-bold text-slate-900 mb-1">Track Specimen</h3>
                                <p className="text-sm text-slate-500">View chain of custody and Check-In.</p>
                            </Card>
                        </Link>

                        <Link href="/results" className="group">
                            <Card className="h-full hover:border-green-400 transition-colors p-6 flex flex-col items-center text-center cursor-pointer bg-slate-50 group-hover:bg-white">
                                <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center text-green-600 mb-4 group-hover:scale-110 transition-transform">
                                    <FileText className="w-6 h-6" />
                                </div>
                                <h3 className="font-bold text-slate-900 mb-1">Enter Results</h3>
                                <p className="text-sm text-slate-500">Input analysis data and verify reports.</p>
                            </Card>
                        </Link>

                        <Link href="/queues" className="group">
                            <Card className="h-full hover:border-purple-400 transition-colors p-6 flex flex-col items-center text-center cursor-pointer bg-slate-50 group-hover:bg-white">
                                <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center text-purple-600 mb-4 group-hover:scale-110 transition-transform">
                                    <Layers className="w-6 h-6" />
                                </div>
                                <h3 className="font-bold text-slate-900 mb-1">Workflow Queues</h3>
                                <p className="text-sm text-slate-500">Manage departmental worklists and validation.</p>
                            </Card>
                        </Link>

                        <Link href="/inventory" className="group">
                            <Card className="h-full hover:border-amber-400 transition-colors p-6 flex flex-col items-center text-center cursor-pointer bg-slate-50 group-hover:bg-white">
                                <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center text-amber-600 mb-4 group-hover:scale-110 transition-transform">
                                    <TrendingUp className="w-6 h-6" />
                                </div>
                                <h3 className="font-bold text-slate-900 mb-1">Inventory</h3>
                                <p className="text-sm text-slate-500">Manage reagents, stock levels and expiry.</p>
                            </Card>
                        </Link>
                    </div>
                </div>

                <div className="space-y-6">
                    <h2 className="text-xl font-bold text-slate-800">System Notifications</h2>
                    <Card className="bg-slate-800 text-white min-h-[300px] flex flex-col">
                        <div className="flex-1 space-y-4">
                            <div className="border-b border-slate-700 pb-2 mb-2">
                                <h3 className="font-bold flex items-center gap-2">
                                    <AlertCircle className="w-4 h-4 text-primary-400" /> Recent Alerts
                                </h3>
                            </div>
                            <div className="text-sm space-y-3 overflow-y-auto max-h-[200px] pr-2 custom-scrollbar">
                                {alerts.length === 0 ? (
                                    <div className="text-slate-400 text-center py-4 italic">No active notifications</div>
                                ) : (
                                    alerts.map(alert => (
                                        <div key={alert.id} className={`p-3 rounded border ${alert.type === 'error' ? 'bg-red-900/20 border-red-900/50 text-red-200' :
                                            alert.type === 'warning' ? 'bg-amber-900/20 border-amber-900/50 text-amber-200' :
                                                'bg-slate-700/50 border-slate-600 text-slate-200'
                                            }`}>
                                            <div className="flex justify-between items-start mb-1">
                                                <div className="text-xs opacity-70 font-mono">
                                                    {new Date(alert.createdAt).toLocaleDateString()}
                                                    {alert.type === 'error' && <span className="ml-2 font-bold text-red-400">CRITICAL</span>}
                                                </div>
                                            </div>
                                            <p>{alert.message}</p>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                        {/* Footer removed as requested */}
                    </Card>
                </div>
            </div>
        </div>
    );
}
