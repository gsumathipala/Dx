"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Trash2, Plus, Ban } from 'lucide-react';

export default function RejectionCriteriaPage() {
    const [criteria, setCriteria] = useState<string[]>([]);
    const [newCriterion, setNewCriterion] = useState('');

    const loadCriteria = async () => {
        const res = await fetch('/api/admin/criteria');
        if (res.ok) setCriteria(await res.json());
    };

    useEffect(() => { loadCriteria(); }, []);

    const handleAdd = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newCriterion) return;
        await fetch('/api/admin/criteria', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ criterion: newCriterion })
        });
        setNewCriterion('');
        loadCriteria();
    };

    const handleDelete = async (criterion: string) => {
        if (!confirm('Remove this criterion?')) return;
        await fetch('/api/admin/criteria', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ criterion })
        });
        loadCriteria();
    };

    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold text-slate-900">Rejection Criteria</h1>
            <p className="text-slate-500">Manage standard reasons for specimen rejection.</p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                    <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                        <Plus className="w-5 h-5 text-primary-600" /> Add Criterion
                    </h2>
                    <form onSubmit={handleAdd} className="flex gap-2">
                        <Input
                            value={newCriterion}
                            onChange={e => setNewCriterion(e.target.value)}
                            placeholder="e.g. Broken Container"
                            required
                        />
                        <Button type="submit">Add</Button>
                    </form>
                </Card>

                <Card>
                    <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                        <Ban className="w-5 h-5 text-red-600" /> Active Criteria
                    </h2>
                    {criteria.length === 0 ? (
                        <p className="text-slate-500 italic">No criteria defined.</p>
                    ) : (
                        <ul className="space-y-2">
                            {criteria.map((c, idx) => (
                                <li key={idx} className="flex justify-between items-center bg-slate-50 p-2 rounded border border-slate-100">
                                    <span className="font-medium">{c}</span>
                                    <button
                                        onClick={() => handleDelete(c)}
                                        className="text-red-400 hover:text-red-600 p-1"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                </Card>
            </div>
        </div>
    );
}
