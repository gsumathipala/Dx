"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Table } from '@/components/ui/Table';
import { formatDateTime } from '@/lib/utils';
import { useAuth } from '@/context/AuthContext';

export default function FeedbackPage() {
    const { user } = useAuth();
    const [items, setItems] = useState<any[]>([]);
    const [showForm, setShowForm] = useState(false);
    const [newItem, setNewItem] = useState({ type: 'Complaint', source: 'Internal', description: '', priority: 'Medium' });

    const loadData = () => {
        fetch('/api/feedback')
            .then(res => res.ok ? res.json() : [])
            .then(setItems)
            .catch(() => setItems([]));
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...newItem,
                investigator: user?.username || 'System'
            })
        });
        setShowForm(false);
        setNewItem({ type: 'Complaint', source: 'Internal', description: '', priority: 'Medium' });
        loadData();
    };

    const handleResolve = async (id: string) => {
        const resolution = prompt("Enter resolution details:");
        if (resolution) {
            await fetch('/api/feedback', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id, status: 'Resolved', resolution })
            });
            loadData();
        }
    };

    const columns = [
        { header: 'Date', accessor: (item: any) => formatDateTime(item.date) },
        { header: 'Type', accessor: (item: any) => <Badge variant={item.type === 'Complaint' ? 'error' : 'success'}>{item.type}</Badge> },
        { header: 'Source', accessor: (item: any) => item.source },
        { header: 'Description', accessor: (item: any) => item.description },
        { header: 'Investigator', accessor: (item: any) => item.investigator },
        { header: 'Status', accessor: (item: any) => <StatusBadge status={item.status} /> },
        { header: 'Resolution', accessor: (item: any) => item.resolution },
        {
            header: 'Result', // "Actions"
            accessor: (item: any) => item.status === 'Open' && (
                <button onClick={() => handleResolve(item.id)} className="text-xs text-blue-600 hover:text-blue-800 font-medium">Resolve</button>
            )
        }
    ];

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold text-slate-900">Feedback & Complaints</h1>
                <button onClick={() => setShowForm(!showForm)} className="btn-primary">
                    + Log New Item
                </button>
            </div>

            {showForm && (
                <Card className="animate-fade-in-down">
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700">Type</label>
                                <select className="input-field" value={newItem.type} onChange={e => setNewItem({ ...newItem, type: e.target.value })}>
                                    <option>Complaint</option>
                                    <option>Concern</option>
                                    <option>Suggestion</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700">Source</label>
                                <select className="input-field" value={newItem.source} onChange={e => setNewItem({ ...newItem, source: e.target.value })}>
                                    <option>Internal (Employee)</option>
                                    <option>External (Client)</option>
                                    <option>Patient</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700">Description</label>
                            <textarea className="input-field h-24" required value={newItem.description} onChange={e => setNewItem({ ...newItem, description: e.target.value })} />
                        </div>
                        <button type="submit" className="btn-primary">Submit Record</button>
                    </form>
                </Card>
            )}

            <Card>
                <Table data={items} columns={columns} keyField="id" emptyMessage="No feedback records found." />
            </Card>
        </div>
    );
}
