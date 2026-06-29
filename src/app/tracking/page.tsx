"use client";

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Search, Package, MapPin, Clock, Activity, Thermometer, AlertTriangle, CheckCircle } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

export default function TrackingPage() {
    const { user } = useAuth();
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<any[]>([]);
    const [searched, setSearched] = useState(false);
    const [loading, setLoading] = useState(false);

    // Action State
    const [actionData, setActionData] = useState<any>({}); // Keyed by spec.id
    const [criteria, setCriteria] = useState<string[]>([]);

    const canEdit = user && ['admin', 'manager', 'scientist', 'clerk', 'medic'].includes(user.role);

    // Load Criteria on Mount
    React.useEffect(() => {
        fetch('/api/admin/criteria')
            .then(res => res.json())
            .then(data => Array.isArray(data) ? setCriteria(data) : setCriteria([]))
            .catch(() => setCriteria([]));
    }, []);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;
        setLoading(true);
        try {
            const res = await fetch(`/api/tracking?q=${encodeURIComponent(query)}`);
            if (res.ok) setResults(await res.json());
        } finally {
            setLoading(false);
            setSearched(true);
        }
    };

    const handleUpdateCustody = async (specId: string) => {
        const data = actionData[specId] || {};
        if (!data.action) return alert('Select an action');

        try {
            const res = await fetch('/api/tracking', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    specimenId: specId,
                    action: data.action,
                    location: data.location,
                    condition: data.condition,
                    temperature: data.temperature,
                    notes: data.notes
                })
            });

            if (res.ok) {
                alert('Custody updated.');
                // Refresh
                handleSearch({ preventDefault: () => { } } as any);
                setActionData({ ...actionData, [specId]: {} }); // Reset form
            } else {
                alert('Update failed');
            }
        } catch (e) { console.error(e); }
    };

    const updateForm = (specId: string, field: string, value: string) => {
        setActionData({
            ...actionData,
            [specId]: { ...actionData[specId], [field]: value }
        });
    };

    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold text-slate-900">Specimen Tracking</h1>
            <p className="text-slate-500">ISO 15189 Chain of Custody & Environmental Monitoring.</p>

            <Card className="bg-slate-50 border-2 border-slate-200">
                <form onSubmit={handleSearch} className="flex gap-4">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-2.5 text-slate-400 w-5 h-5" />
                        <Input
                            className="pl-10 h-10 bg-white text-lg"
                            placeholder="Scan Barcode / Specimen ID / Patient Name..."
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            autoFocus
                        />
                    </div>
                    <Button type="submit" disabled={loading} className="h-12 px-8">
                        {loading ? 'Searching...' : 'Track'}
                    </Button>
                </form>
            </Card>

            {searched && results.length === 0 && (
                <div className="text-center py-12 text-slate-500 bg-white rounded border border-dashed">
                    <Package className="w-12 h-12 mx-auto mb-2 opacity-20" />
                    <p>No specimens found matching &quot;{query}&quot;</p>
                </div>
            )}

            <div className="grid gap-6">
                {results.map((spec) => (
                    <Card key={spec.id} className="overflow-hidden">
                        <div className="flex flex-col xl:flex-row gap-6">
                            {/* Summary & Form */}
                            <div className="flex-1 space-y-6">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <h2 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                                            <Package className="w-6 h-6 text-primary-600" />
                                            {spec.id}
                                        </h2>
                                        <p className="text-lg text-slate-600 font-medium">{spec.type} - {spec.patientName}</p>
                                        <p className="text-sm text-slate-400 font-mono">{spec.patientMrn}</p>
                                    </div>
                                    <div className={`px-4 py-2 rounded-full font-bold text-sm uppercase tracking-wide
                                        ${spec.status === 'received' ? 'bg-green-100 text-green-800' :
                                            spec.status === 'disposed' ? 'bg-slate-200 text-slate-600' : 'bg-blue-50 text-blue-800'}`}>
                                        {spec.status}
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div className="bg-slate-50 p-3 rounded">
                                        <div className="text-slate-500 flex items-center gap-1"><Clock className="w-3 h-3" /> Collected</div>
                                        <div className="font-medium">{spec.collectionDate ? new Date(spec.collectionDate).toLocaleString() : 'N/A'}</div>
                                    </div>
                                    <div className="bg-blue-50 p-3 rounded border border-blue-100">
                                        <div className="text-blue-500 flex items-center gap-1"><MapPin className="w-3 h-3" /> Location</div>
                                        <div className="font-bold text-blue-900">{spec.location || 'In Transit'}</div>
                                    </div>
                                    {spec.condition && (
                                        <div className="bg-amber-50 p-3 rounded border border-amber-100 col-span-2 flex gap-2 items-center text-amber-800">
                                            <AlertTriangle className="w-4 h-4" />
                                            <span>Condition Note: <strong>{spec.condition}</strong></span>
                                        </div>
                                    )}
                                </div>

                                {canEdit && (
                                    <div className="bg-slate-50 p-4 rounded border border-slate-200 mt-4 animate-in fade-in">
                                        <h4 className="font-bold text-slate-700 mb-3 flex items-center gap-2">
                                            <CheckCircle className="w-4 h-4 text-green-600" /> Update Custody
                                        </h4>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                                            <div className="space-y-1">
                                                <Label>Event Type</Label>
                                                <select
                                                    className="w-full border rounded p-2 text-sm bg-white"
                                                    value={actionData[spec.id]?.action || ''}
                                                    onChange={e => updateForm(spec.id, 'action', e.target.value)}
                                                >
                                                    <option value="">Select Action...</option>
                                                    <option value="CHECK_IN">Check-In (Scan)</option>
                                                    <option value="CHECK_OUT">Check-Out / Transfer</option>
                                                    <option value="CONDITION_UPDATE">Update Integrity</option>
                                                    <option value="REJECT">Reject Specimen</option>
                                                    <option value="DISPOSE">Dispose / Archive</option>
                                                </select>
                                            </div>

                                            {actionData[spec.id]?.action === 'REJECT' ? (
                                                <div className="space-y-1">
                                                    <Label className="text-red-600">Rejection Reason</Label>
                                                    <select
                                                        className="w-full border border-red-200 rounded p-2 text-sm bg-red-50"
                                                        value={actionData[spec.id]?.condition || ''} // Reusing condition field for reason
                                                        onChange={e => updateForm(spec.id, 'condition', e.target.value)}
                                                    >
                                                        <option value="">Select Reason...</option>
                                                        {criteria.map(c => <option key={c} value={c}>{c}</option>)}
                                                    </select>
                                                </div>
                                            ) : (
                                                <div className="space-y-1">
                                                    <Label>New Location</Label>
                                                    <Input
                                                        placeholder="e.g. Fridge 2, Shelf A"
                                                        value={actionData[spec.id]?.location || ''}
                                                        onChange={e => updateForm(spec.id, 'location', e.target.value)}
                                                        className="bg-white"
                                                    />
                                                </div>
                                            )}

                                            {actionData[spec.id]?.action !== 'REJECT' && (
                                                <div className="space-y-1">
                                                    <Label>Condition</Label>
                                                    <select
                                                        className="w-full border rounded p-2 text-sm bg-white"
                                                        value={actionData[spec.id]?.condition || ''}
                                                        onChange={e => updateForm(spec.id, 'condition', e.target.value)}
                                                    >
                                                        <option value="">Unchanged</option>
                                                        <option value="Good">Good / Normal</option>
                                                        <option value="Hemolyzed">Hemolyzed</option>
                                                        <option value="Lipemic">Lipemic</option>
                                                        <option value="Leaking">Leaking / Damaged</option>
                                                        <option value="Thawed">Thawed</option>
                                                    </select>
                                                </div>
                                            )}
                                            <div className="space-y-1">
                                                <Label>Temp (°C)</Label>
                                                <div className="relative">
                                                    <Thermometer className="absolute left-2.5 top-2.5 w-4 h-4 text-slate-400" />
                                                    <Input
                                                        className="pl-8 bg-white"
                                                        placeholder="e.g. -20"
                                                        value={actionData[spec.id]?.temperature || ''}
                                                        onChange={e => updateForm(spec.id, 'temperature', e.target.value)}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                        <Input
                                            placeholder="Notes / Operator Comments..."
                                            value={actionData[spec.id]?.notes || ''}
                                            onChange={e => updateForm(spec.id, 'notes', e.target.value)}
                                            className="bg-white mb-3"
                                        />
                                        <Button
                                            onClick={() => handleUpdateCustody(spec.id)}
                                            className="w-full bg-slate-800 hover:bg-slate-700"
                                            disabled={!actionData[spec.id]?.action}
                                        >
                                            Log Custody Event
                                        </Button>
                                    </div>
                                )}
                            </div>

                            {/* Timeline */}
                            <div className="flex-1 xl:max-w-md border-l pl-6 border-slate-100 flex flex-col h-full">
                                <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2 Sticky top-0">
                                    <Activity className="w-4 h-4" /> Comprehensive Audit Trail
                                </h3>

                                <div className="space-y-6 flex-1 overflow-y-auto max-h-[500px] pr-2 custom-scrollbar">
                                    {spec.history && spec.history.length > 0 ? (
                                        spec.history.map((h: any, idx: number) => {
                                            let details = null;
                                            try { details = h.details ? JSON.parse(h.details) : null; } catch (e) { }

                                            return (
                                                <div key={idx} className="relative pl-6 border-l-2 border-slate-200 last:border-0 pb-4">
                                                    <div className={`absolute -left-[9px] top-0 w-4 h-4 rounded-full border-2 border-white 
                                                        ${h.action === 'DISPOSE' ? 'bg-red-500' : 'bg-primary-500'}`}></div>

                                                    <div className="text-sm font-bold text-slate-800 flex justify-between">
                                                        <span>{h.action}</span>
                                                        {details?.temp && <span className="text-xs font-normal bg-slate-100 px-1 rounded flex items-center">{details.temp}°C</span>}
                                                    </div>

                                                    <div className="text-xs text-slate-500 mb-1">{new Date(h.timestamp).toLocaleString()}</div>
                                                    <div className="text-xs text-slate-600 font-medium">By: {h.user}</div>

                                                    {details && (
                                                        <div className="mt-2 text-xs bg-slate-50 p-2 rounded border border-slate-100 space-y-1">
                                                            {details.location && <div>📍 {details.location}</div>}
                                                            {details.condition && <div className="text-amber-700">⚠️ {details.condition}</div>}
                                                            {details.notes && <div className="italic text-slate-500">&quot;{details.notes}&quot;</div>}
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })
                                    ) : (
                                        <div className="text-sm text-slate-400 italic">No tracking history available.</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </Card>
                ))}
            </div>
        </div>
    );
}
