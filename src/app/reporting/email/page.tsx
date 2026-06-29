"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Mail, Trash2, Send, CheckCircle, AlertCircle } from 'lucide-react';

export default function EmailQueuePage() {
    const [queue, setQueue] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState<string[]>([]);
    const [sending, setSending] = useState(false);

    useEffect(() => {
        loadQueue();
    }, []);

    const loadQueue = async () => {
        const res = await fetch('/api/reporting/email');
        if (res.ok) setQueue(await res.json());
        setLoading(false);
    };

    const toggleSelect = (id: string) => {
        if (selected.includes(id)) {
            setSelected(selected.filter(s => s !== id));
        } else {
            setSelected([...selected, id]);
        }
    };

    const handleRemove = async (id: string) => {
        if (!confirm('Remove from email queue?')) return;
        await fetch('/api/reporting/email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'REMOVE', id })
        });
        loadQueue();
    };

    const handleSendBatch = async () => {
        if (selected.length === 0) return;
        if (!confirm(`Are you sure you want to email ${selected.length} reports using the External Provider?`)) return;

        setSending(true);
        try {
            const res = await fetch('/api/reporting/email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'SEND_BATCH', items: selected })
            });
            const data = await res.json();
            alert('Batch processing complete.');
            setSelected([]);
            loadQueue();
        } catch (e) {
            alert('Error sending emails');
        } finally {
            setSending(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Email Report Delivery</h1>
                    <p className="text-slate-500">Queue and batch send patient results to external emails.</p>
                </div>
                <div className="flex gap-3">
                    <Button
                        onClick={handleSendBatch}
                        disabled={selected.length === 0 || sending}
                        className="bg-blue-600 hover:bg-blue-700 text-white"
                    >
                        {sending ? 'Sending...' : <><Send className="w-4 h-4 mr-2" /> Send Selected ({selected.length})</>}
                    </Button>
                </div>
            </div>

            <Card>
                <div className="p-0 overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50 text-slate-500 font-medium border-b">
                            <tr>
                                <th className="p-4 w-10">
                                    <input
                                        type="checkbox"
                                        onChange={(e) => setSelected(e.target.checked ? queue.map(i => i.id) : [])}
                                        checked={selected.length === queue.length && queue.length > 0}
                                    />
                                </th>
                                <th className="p-4">Patient</th>
                                <th className="p-4">Accession / Check-In</th>
                                <th className="p-4">Recipient Email</th>
                                <th className="p-4">Queued By</th>
                                <th className="p-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y">
                            {queue.length === 0 && !loading && (
                                <tr>
                                    <td colSpan={6} className="p-8 text-center text-slate-400">
                                        The email queue is empty.
                                    </td>
                                </tr>
                            )}
                            {queue.map(item => (
                                <tr key={item.id} className="hover:bg-slate-50">
                                    <td className="p-4">
                                        <input
                                            type="checkbox"
                                            checked={selected.includes(item.id)}
                                            onChange={() => toggleSelect(item.id)}
                                        />
                                    </td>
                                    <td className="p-4 font-medium text-slate-900">{item.patientName}</td>
                                    <td className="p-4">
                                        <div className="font-mono text-xs">{item.accessionNumber}</div>
                                        <div className="text-xs text-slate-500">{new Date(item.addedAt).toLocaleDateString()}</div>
                                    </td>
                                    <td className="p-4">
                                        {item.recipientEmail ? (
                                            <span className="flex items-center gap-2 text-slate-700">
                                                <Mail className="w-3 h-3 text-slate-400" /> {item.recipientEmail}
                                            </span>
                                        ) : (
                                            <span className="flex items-center gap-2 text-red-500 font-bold">
                                                <AlertCircle className="w-3 h-3" /> Missing Email
                                            </span>
                                        )}
                                    </td>
                                    <td className="p-4 text-slate-500">{item.addedBy}</td>
                                    <td className="p-4 text-right">
                                        <button onClick={() => handleRemove(item.id)} className="text-slate-400 hover:text-red-500">
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </Card>
        </div>
    );
}
