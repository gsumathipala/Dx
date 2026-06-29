"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertCircle, Info, CheckCircle, XCircle, Megaphone } from 'lucide-react';
import { Table } from '@/components/ui/Table';

export default function AlertLogPage() {
    const [alerts, setAlerts] = useState<any[]>([]);
    const [newAlert, setNewAlert] = useState({ message: '', type: 'info' });
    const [loading, setLoading] = useState(false);

    useEffect(() => { loadAlerts(); }, []);

    const loadAlerts = async () => {
        const res = await fetch('/api/admin/alerts');
        if (res.ok) setAlerts(await res.json());
    };

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            await fetch('/api/admin/alerts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newAlert)
            });
            setNewAlert({ message: '', type: 'info' });
            loadAlerts();
        } finally { setLoading(false); }
    };

    const toggleActive = async (id: string, current: boolean) => {
        await fetch('/api/admin/alerts', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, active: !current })
        });
        loadAlerts();
    };

    const columns = [
        {
            header: 'Status', accessor: (d: any) => (
                <button
                    onClick={() => toggleActive(d.id, d.active)}
                    className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-bold ${d.active ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}
                >
                    {d.active ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                    {d.active ? 'Active' : 'Inactive'}
                </button>
            )
        },
        {
            header: 'Type', accessor: (d: any) => (
                <span className={`uppercase text-xs font-bold ${d.type === 'warning' ? 'text-amber-600' : d.type === 'error' ? 'text-red-600' : 'text-blue-600'}`}>
                    {d.type}
                </span>
            )
        },
        { header: 'Message', accessor: (d: any) => d.message },
        {
            header: 'Created By', accessor: (d: any) => (
                <div className="text-xs">
                    <div className="font-bold">{d.createdBy || 'System'}</div>
                    <div className="text-slate-400">{new Date(d.createdAt).toLocaleString()}</div>
                </div>
            )
        },
        {
            header: 'Reach', accessor: (d: any) => (
                <span className="text-xs bg-slate-100 px-2 py-1 rounded">
                    Read by {d.readBy?.length || 0}
                </span>
            )
        }
    ];

    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold text-slate-900">System Alert Log</h1>
            <p className="text-slate-500">Universal log of system-wide broadcasts. Manage active alerts.</p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="md:col-span-1 border-t-4 border-t-primary-500 h-fit">
                    <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                        <Megaphone className="w-5 h-5 text-primary-600" /> Broadcast Alert
                    </h2>
                    <form onSubmit={handleCreate} className="space-y-4">
                        <div className="space-y-2">
                            <Label>Message</Label>
                            <Input
                                value={newAlert.message}
                                onChange={e => setNewAlert({ ...newAlert, message: e.target.value })}
                                placeholder="e.g. Server maintenance..."
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Type</Label>
                            <select
                                className="w-full border rounded p-2"
                                value={newAlert.type}
                                onChange={e => setNewAlert({ ...newAlert, type: e.target.value })}
                            >
                                <option value="info">Info (Blue)</option>
                                <option value="warning">Warning (Amber)</option>
                                <option value="error">Critical (Red)</option>
                            </select>
                        </div>
                        <Button type="submit" disabled={loading} className="w-full">Broadcast</Button>
                    </form>
                </Card>

                <div className="md:col-span-2">
                    <Card>
                        <Table data={alerts} columns={columns} keyField="id" />
                    </Card>
                </div>
            </div>
        </div>
    );
}
