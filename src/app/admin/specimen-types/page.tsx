"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Trash2, Edit2, AlertTriangle, Plus } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function SpecimenTypesPage() {
    const [types, setTypes] = useState<string[]>([]);
    const [newType, setNewType] = useState('');
    const [loading, setLoading] = useState(false);
    const [renameMode, setRenameMode] = useState<{ old: string, new: string } | null>(null);
    const [message, setMessage] = useState<{ type: 'success' | 'error' | 'warning', text: string } | null>(null);

    useEffect(() => { loadTypes(); }, []);

    const loadTypes = async () => {
        const res = await fetch('/api/admin/specimen-types');
        if (res.ok) setTypes(await res.json());
    };

    const handleAdd = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);
        try {
            const res = await fetch('/api/admin/specimen-types', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: newType })
            });
            if (res.ok) {
                setNewType('');
                loadTypes();
                setMessage({ type: 'success', text: 'Specimen type added.' });
            } else {
                setMessage({ type: 'error', text: 'Failed to add type.' });
            }
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (type: string) => {
        if (!confirm(`Delete '${type}'?`)) return;

        setLoading(true);
        setMessage(null);
        const res = await fetch(`/api/admin/specimen-types?type=${type}`, { method: 'DELETE' });

        if (res.ok) {
            setMessage({ type: 'success', text: 'Type deleted.' });
            loadTypes();
        } else if (res.status === 409) {
            const data = await res.json();
            // Requirement: "Cautioned... instead provision to rename"
            setMessage({
                type: 'warning',
                text: `${data.message} Please REMAIN CAUTIOUS. We recommend renaming instead of deleting to preserve data integrity.`
            });
            // Automatically switch to rename mode for this item
            setRenameMode({ old: type, new: type });
        } else {
            setMessage({ type: 'error', text: 'Operation failed.' });
        }
        setLoading(false);
    };

    const handleRename = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!renameMode) return;

        setLoading(true);
        setMessage(null);

        const res = await fetch('/api/admin/specimen-types', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ oldType: renameMode.old, newType: renameMode.new })
        });

        if (res.ok) {
            const data = await res.json();
            setMessage({ type: 'success', text: data.message });
            setRenameMode(null);
            loadTypes();
        } else {
            const data = await res.json();
            setMessage({ type: 'error', text: data.error });
        }
        setLoading(false);
    };

    return (
        <div className="max-w-4xl mx-auto space-y-6 pb-12">
            <h1 className="text-3xl font-bold text-slate-900">Specimen Types</h1>
            <p className="text-slate-500">Manage standard sample types (e.g., Serum, Urine). Changes here cascade to test definitions.</p>

            {message && (
                <Alert variant={message.type === 'error' ? 'destructive' : 'default'} className={message.type === 'warning' ? 'bg-amber-50 border-amber-200 text-amber-800' : ''}>
                    {message.type === 'warning' ? <AlertTriangle className="h-4 w-4 text-amber-600" /> : null}
                    <AlertTitle>{message.type.toUpperCase()}</AlertTitle>
                    <AlertDescription>{message.text}</AlertDescription>
                </Alert>
            )}

            <div className="grid md:grid-cols-2 gap-6">
                <Card title="Add New Type">
                    <form onSubmit={handleAdd} className="flex gap-2">
                        <Input
                            placeholder="e.g. Plasma (EDTA)"
                            value={newType}
                            onChange={e => setNewType(e.target.value)}
                            required
                        />
                        <Button type="submit" disabled={loading}>
                            <Plus className="w-4 h-4 mr-1" /> Add
                        </Button>
                    </form>
                </Card>

                <Card title="Master List" className="md:col-span-2">
                    <div className="space-y-2">
                        {types.map((type) => (
                            <div key={type} className="flex justify-between items-center p-3 bg-slate-50 rounded border border-slate-100 hover:border-slate-300 transition-colors">
                                {renameMode?.old === type ? (
                                    <form onSubmit={handleRename} className="flex-1 flex gap-2 items-center">
                                        <Input
                                            value={renameMode.new}
                                            onChange={e => setRenameMode({ ...renameMode, new: e.target.value })}
                                            autoFocus
                                            className="bg-white"
                                        />
                                        <Button type="submit" className="h-8 px-3">Save</Button>
                                        <Button type="button" variant="outline" className="h-8 px-3 border-0" onClick={() => setRenameMode(null)}>Cancel</Button>
                                    </form>
                                ) : (
                                    <>
                                        <span className="font-medium text-slate-700">{type}</span>
                                        <div className="flex gap-2">
                                            <Button variant="outline" className="h-8 px-3 border-0" onClick={() => setRenameMode({ old: type, new: type })}>
                                                <Edit2 className="w-4 h-4 text-slate-500" />
                                            </Button>
                                            <Button variant="outline" className="h-8 px-3 border-0" onClick={() => handleDelete(type)}>
                                                <Trash2 className="w-4 h-4 text-red-400 hover:text-red-600" />
                                            </Button>
                                        </div>
                                    </>
                                )}
                            </div>
                        ))}
                    </div>
                </Card>
            </div>
        </div>
    );
}
