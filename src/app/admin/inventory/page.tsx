"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Package, AlertTriangle, Building2, Layers } from 'lucide-react';

export default function InventoryPage() {
    const [items, setItems] = useState<any[]>([]);
    const [departments, setDepartments] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);

    // Form State
    const [newItem, setNewItem] = useState({
        name: '', catalogNumber: '', lotNumber: '',
        expiry: '', quantity: 0, unit: 'kits', departmentId: ''
    });

    useEffect(() => {
        Promise.all([
            fetch('/api/admin/inventory').then(r => r.json()),
            fetch('/api/admin/departments').then(r => r.json()) // Only enabled departments for allocation
        ]).then(([itemsData, deptsData]) => {
            setItems(itemsData);
            setDepartments(deptsData);
            setLoading(false);
        });
    }, []);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        const res = await fetch('/api/admin/inventory', {
            method: 'POST',
            body: JSON.stringify(newItem)
        });
        if (res.ok) {
            setItems([...items, await res.json()]);
            setShowAdd(false);
            setNewItem({
                name: '', catalogNumber: '', lotNumber: '',
                expiry: '', quantity: 0, unit: 'kits', departmentId: ''
            });
        }
    };

    const getDeptName = (id: string) => {
        if (!id) return 'Shared / All Labs';
        const d = departments.find(d => d.id === id);
        return d ? d.name : 'Unknown';
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Inventory Management</h1>
                    <p className="text-slate-500">Track reagents, kits, and consumables across laboratories.</p>
                </div>
                <Button onClick={() => setShowAdd(!showAdd)} className="bg-primary-600">
                    <Package className="w-4 h-4 mr-2" /> Receive Item
                </Button>
            </div>

            {showAdd && (
                <Card title="Receive New Inventory" className="border-l-4 border-l-primary-500">
                    <form onSubmit={handleCreate} className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="label">Item Name</label>
                                <Input required value={newItem.name} onChange={e => setNewItem({ ...newItem, name: e.target.value })} placeholder="e.g. TSH Reagent Pack" />
                            </div>
                            <div>
                                <label className="label">Catalog #</label>
                                <Input value={newItem.catalogNumber} onChange={e => setNewItem({ ...newItem, catalogNumber: e.target.value })} />
                            </div>
                            <div>
                                <label className="label">Lot Number</label>
                                <Input required value={newItem.lotNumber} onChange={e => setNewItem({ ...newItem, lotNumber: e.target.value })} />
                            </div>
                            <div>
                                <label className="label">Expiry Date</label>
                                <Input type="date" required value={newItem.expiry} onChange={e => setNewItem({ ...newItem, expiry: e.target.value })} />
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                                <div>
                                    <label className="label">Quantity</label>
                                    <Input type="number" required value={newItem.quantity} onChange={e => setNewItem({ ...newItem, quantity: Number(e.target.value) })} />
                                </div>
                                <div>
                                    <label className="label">Unit</label>
                                    <select className="input-field" value={newItem.unit} onChange={e => setNewItem({ ...newItem, unit: e.target.value })}>
                                        <option value="kits">Kits</option>
                                        <option value="boxes">Boxes</option>
                                        <option value="units">Units</option>
                                        <option value="liters">Liters</option>
                                    </select>
                                </div>
                            </div>
                            <div>
                                <label className="label">Department (Allocation)</label>
                                <select className="input-field" value={newItem.departmentId} onChange={e => setNewItem({ ...newItem, departmentId: e.target.value })}>
                                    <option value="">-- Shared / Central Store --</option>
                                    {departments.map(d => (
                                        <option key={d.id} value={d.id}>{d.name}</option>
                                    ))}
                                </select>
                            </div>
                        </div>
                        <div className="flex justify-end gap-2">
                            <Button type="button" variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button>
                            <Button type="submit">Add to Inventory</Button>
                        </div>
                    </form>
                </Card>
            )}

            <Card className="overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 border-b text-slate-500">
                        <tr>
                            <th className="p-3">Item Name</th>
                            <th className="p-3">Lot / Expiry</th>
                            <th className="p-3">Allocation</th>
                            <th className="p-3 text-right">Qty</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y">
                        {items.map(item => (
                            <tr key={item.id} className="hover:bg-slate-50">
                                <td className="p-3 font-medium text-slate-900">{item.name}</td>
                                <td className="p-3">
                                    <div className="flex flex-col text-xs">
                                        <span>Lot: {item.lotNumber}</span>
                                        <span className={new Date(item.expiry) < new Date() ? 'text-red-600 font-bold' : 'text-slate-500'}>
                                            Exp: {item.expiry}
                                        </span>
                                    </div>
                                </td>
                                <td className="p-3">
                                    <span className={`px-2 py-1 rounded text-xs font-bold ${!item.departmentId ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-600'}`}>
                                        {getDeptName(item.departmentId)}
                                    </span>
                                </td>
                                <td className="p-3 text-right font-mono font-bold">{item.quantity} {item.unit}</td>
                            </tr>
                        ))}
                        {items.length === 0 && !loading && (
                            <tr><td colSpan={4} className="p-8 text-center text-slate-400">No inventory items found.</td></tr>
                        )}
                    </tbody>
                </table>
            </Card>
        </div>
    );
}
