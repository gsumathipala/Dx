"use client";

import React, { useState, useEffect } from 'react';
import { formatDate } from '@/lib/utils';
import { Card } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Table } from '@/components/ui/Table';

type InventoryItem = {
    id: string;
    name: string;
    lotNumber: string;
    expiryDate: string;
    quantity: number;
    lowStockThreshold: number;
    unit: string;
};

export default function InventoryPage() {
    const [items, setItems] = useState<InventoryItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [newItem, setNewItem] = useState({
        name: '', lotNumber: '', expiryDate: '', quantity: 0, lowStockThreshold: 10, unit: 'kits'
    });

    useEffect(() => {
        loadItems();
    }, []);

    const loadItems = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/inventory');
            if (res.ok) setItems(await res.json());
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        const res = await fetch('/api/inventory', {
            method: 'POST',
            body: JSON.stringify(newItem)
        });
        if (res.ok) {
            setNewItem({ name: '', lotNumber: '', expiryDate: '', quantity: 0, lowStockThreshold: 10, unit: 'kits' });
            setShowForm(false);
            loadItems();
        }
    };

    const handleUpdateQuantity = async (id: string, currentQty: number, change: number) => {
        const newQty = currentQty + change;
        if (newQty < 0) return;
        await fetch(`/api/inventory/${id}`, {
            method: 'PUT',
            body: JSON.stringify({ quantity: newQty })
        });
        loadItems();
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Are you sure?')) return;
        await fetch(`/api/inventory/${id}`, { method: 'DELETE' });
        loadItems();
    };

    const getStatus = (item: InventoryItem) => {
        const now = new Date();
        const expiry = new Date(item.expiryDate);
        if (expiry < now) return 'Expired';
        if (item.quantity <= item.lowStockThreshold) return 'Low Stock';
        const daysToExpiry = Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 3600 * 24));
        if (daysToExpiry < 30) return `Expiring in ${daysToExpiry}d`;
        return 'OK';
    };

    const columns = [
        {
            header: 'Status',
            accessor: (item: InventoryItem) => <StatusBadge status={getStatus(item)} />
        },
        {
            header: 'Item Details',
            accessor: (item: InventoryItem) => (
                <div>
                    <div className="font-medium text-slate-900">{item.name}</div>
                    <div className="text-xs text-slate-500">Lot: {item.lotNumber}</div>
                </div>
            )
        },
        {
            header: 'Expiry',
            accessor: (item: InventoryItem) => <span className="text-slate-600">{formatDate(item.expiryDate)}</span>
        },
        {
            header: 'Quantity',
            accessor: (item: InventoryItem) => (
                <div className="flex items-center gap-2">
                    <button onClick={() => handleUpdateQuantity(item.id, item.quantity, -1)} className="w-6 h-6 flex items-center justify-center rounded bg-slate-100 hover:bg-red-50 text-slate-600 hover:text-red-600 font-bold transition-colors">-</button>
                    <span className={`w-16 text-center font-mono ${item.quantity <= item.lowStockThreshold ? 'text-red-600 font-bold' : 'text-slate-700'}`}>
                        {item.quantity} <span className="text-xs font-normal text-slate-400">{item.unit}</span>
                    </span>
                    <button onClick={() => handleUpdateQuantity(item.id, item.quantity, 1)} className="w-6 h-6 flex items-center justify-center rounded bg-slate-100 hover:bg-green-50 text-slate-600 hover:text-green-600 font-bold transition-colors">+</button>
                </div>
            )
        },
        {
            header: 'Action',
            accessor: (item: InventoryItem) => (
                <button onClick={() => handleDelete(item.id)} className="text-xs text-red-500 hover:text-red-700 font-medium">
                    Remove
                </button>
            )
        }
    ];

    if (loading) return <div className="p-8">Loading...</div>;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold tracking-tight text-slate-900">Inventory Management</h1>
                <button
                    onClick={() => setShowForm(!showForm)}
                    className="btn-primary"
                >
                    {showForm ? 'Cancel' : 'Add New Reagent'}
                </button>
            </div>

            {showForm && (
                <Card title="Add New Reagent" className="mb-6 animate-fade-in-down">
                    <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-700">Reagent Name</label>
                            <input type="text" required className="input-field"
                                value={newItem.name} onChange={e => setNewItem({ ...newItem, name: e.target.value })} />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700">Lot Number</label>
                            <input type="text" required className="input-field"
                                value={newItem.lotNumber} onChange={e => setNewItem({ ...newItem, lotNumber: e.target.value })} />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700">Expiry Date</label>
                            <input type="date" required className="input-field"
                                value={newItem.expiryDate} onChange={e => setNewItem({ ...newItem, expiryDate: e.target.value })} />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700">Initial Quantity</label>
                                <input type="number" required min="0" className="input-field"
                                    value={newItem.quantity} onChange={e => setNewItem({ ...newItem, quantity: +e.target.value })} />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700">Unit</label>
                                <input type="text" required className="input-field" placeholder="e.g. kits"
                                    value={newItem.unit} onChange={e => setNewItem({ ...newItem, unit: e.target.value })} />
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700">Low Stock Limit</label>
                            <input type="number" required min="0" className="input-field"
                                value={newItem.lowStockThreshold} onChange={e => setNewItem({ ...newItem, lowStockThreshold: +e.target.value })} />
                        </div>
                        <div className="md:col-span-2 pt-2">
                            <button type="submit" className="btn-primary w-full md:w-auto">Save to Inventory</button>
                        </div>
                    </form>
                </Card>
            )}

            <Card>
                <Table
                    data={items}
                    columns={columns}
                    keyField="id"
                    emptyMessage="Inventory is empty."
                />
            </Card>
        </div>
    );
}
