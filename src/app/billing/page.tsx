"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { formatDateTime } from '@/lib/utils';

export default function BillingPage() {
    const [invoices, setInvoices] = useState<any[]>([]);
    const [currency, setCurrency] = useState('$');

    const loadData = async () => {
        fetch('/api/billing')
            .then(r => r.json())
            .then(data => Array.isArray(data) ? setInvoices(data) : setInvoices([]))
            .catch(() => setInvoices([]));
        fetch('/api/admin/settings').then(r => r.json()).then(data => {
            if (data?.currencySymbol) setCurrency(data.currencySymbol);
        }).catch(() => { });
    };

    useEffect(() => { loadData(); }, []);

    const handleMarkPaid = async (orderId: string) => {
        await fetch('/api/billing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ orderId, action: 'mark_paid' })
        });
        loadData();
    };

    const totalRevenue = invoices.filter(i => i.paymentStatus === 'Paid').reduce((acc, curr) => acc + curr.total, 0);
    const pendingRevenue = invoices.filter(i => i.paymentStatus !== 'Paid').reduce((acc, curr) => acc + curr.total, 0);

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold text-slate-900">Billing & Financials (Revenue Cycle)</h1>

            {/* Stats Cards */}
            <div className="grid grid-cols-3 gap-6">
                <Card className="bg-green-50 border-green-200">
                    <h3 className="text-green-800 font-bold">Total Collected</h3>
                    <p className="text-3xl font-bold text-green-700">{currency}{totalRevenue.toLocaleString()}</p>
                </Card>
                <Card className="bg-amber-50 border-amber-200">
                    <h3 className="text-amber-800 font-bold">Outstanding (AR)</h3>
                    <p className="text-3xl font-bold text-amber-700">{currency}{pendingRevenue.toLocaleString()}</p>
                </Card>
                <Card>
                    <h3 className="text-slate-800 font-bold">Total Invoices</h3>
                    <p className="text-3xl font-bold text-slate-700">{invoices.length}</p>
                </Card>
            </div>

            <Card title="Invoice Register">
                <table className="w-full text-left text-sm">
                    <thead>
                        <tr className="border-b text-slate-500">
                            <th className="py-2">Invoice #</th>
                            <th className="py-2">Patient</th>
                            <th className="py-2">Date</th>
                            <th className="py-2">Services</th>
                            <th className="py-2 text-right">Amount</th>
                            <th className="py-2 text-center">Status</th>
                            <th className="py-2 text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {invoices.map(inv => (
                            <tr key={inv.id} className="border-b hover:bg-slate-50">
                                <td className="py-3 font-mono font-bold">INV-{inv.accessionNumber}</td>
                                <td className="py-3">{inv.patientName}</td>
                                <td className="py-3">{formatDateTime(inv.timestamp)}</td>
                                <td className="py-3 text-xs text-slate-500 max-w-xs truncate">
                                    {inv.lineItems.map((i: any) => `${i.name} (${currency}${i.price})`).join(', ')}
                                </td>
                                <td className="py-3 text-right font-bold text-slate-800">{currency}{inv.total}</td>
                                <td className="py-3 text-center">
                                    <Badge variant={inv.paymentStatus === 'Paid' ? 'success' : 'error'}>{inv.paymentStatus}</Badge>
                                </td>
                                <td className="py-3 text-right">
                                    {inv.paymentStatus !== 'Paid' && (
                                        <button onClick={() => handleMarkPaid(inv.id)} className="text-green-600 font-bold hover:underline">
                                            Mark Paid 💳
                                        </button>
                                    )}
                                    {inv.paymentStatus === 'Paid' && (
                                        <span className="text-slate-400 text-xs">Paid on {new Date(inv.paymentDate).toLocaleDateString()}</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </Card>
        </div>
    );
}
