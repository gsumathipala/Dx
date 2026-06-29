"use client";

import React, { useState, useEffect } from 'react';
import type { Aliquot, AliquotCreate } from '@/types/aliquot';
import { formatDateTime } from '@/lib/utils';
import { useAuth } from '@/context/AuthContext';

interface AliquotManagerProps {
    parentSampleId: string;
    parentAccessionNumber: string;
    parentSampleType: string;
    onAliquotCreated?: (aliquots: Aliquot[]) => void;
}

export function AliquotManager({
    parentSampleId,
    parentAccessionNumber,
    parentSampleType,
    onAliquotCreated
}: AliquotManagerProps) {
    const { user } = useAuth();
    const [aliquots, setAliquots] = useState<Aliquot[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [formData, setFormData] = useState({
        type: parentSampleType,
        volume: '',
        volumeUnit: 'mL',
        containerId: '',
        location: '',
        purpose: '',
        count: 1
    });

    useEffect(() => {
        loadAliquots();
    }, [parentSampleId]);

    const loadAliquots = async () => {
        setLoading(true);
        try {
            const res = await fetch(`/api/samples/aliquot?parentSampleId=${parentSampleId}`);
            if (res.ok) {
                const data = await res.json();
                setAliquots(data);
            }
        } catch (error) {
            console.error('Failed to load aliquots:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateAliquots = async (e: React.FormEvent) => {
        e.preventDefault();

        const payload: AliquotCreate = {
            parentSampleId,
            parentAccessionNumber,
            type: formData.type,
            volume: formData.volume ? parseFloat(formData.volume) : undefined,
            volumeUnit: formData.volumeUnit,
            containerId: formData.containerId || undefined,
            location: formData.location,
            createdBy: user?.username || 'unknown',
            createdByName: user?.name || 'Unknown User',
            purpose: formData.purpose || undefined,
            count: formData.count
        };

        try {
            const res = await fetch('/api/samples/aliquot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const newAliquots = await res.json();
                await loadAliquots();
                setShowForm(false);
                setFormData({
                    type: parentSampleType,
                    volume: '',
                    volumeUnit: 'mL',
                    containerId: '',
                    location: '',
                    purpose: '',
                    count: 1
                });
                if (onAliquotCreated) {
                    onAliquotCreated(Array.isArray(newAliquots) ? newAliquots : [newAliquots]);
                }
            } else {
                alert('Failed to create aliquot(s)');
            }
        } catch (error) {
            console.error('Error creating aliquots:', error);
            alert('Error creating aliquot(s)');
        }
    };

    const handleUpdateStatus = async (aliquotId: string, newStatus: 'Used' | 'Disposed') => {
        if (!confirm(`Mark this aliquot as ${newStatus}?`)) return;

        try {
            const res = await fetch('/api/samples/aliquot', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: aliquotId,
                    status: newStatus,
                    performedBy: user?.username,
                    performedByName: user?.name
                })
            });

            if (res.ok) {
                await loadAliquots();
            } else {
                alert('Failed to update aliquot status');
            }
        } catch (error) {
            console.error('Error updating aliquot:', error);
            alert('Error updating aliquot');
        }
    };

    const activeAliquots = aliquots.filter(a => a.status === 'Active');
    const usedAliquots = aliquots.filter(a => a.status === 'Used');
    const disposedAliquots = aliquots.filter(a => a.status === 'Disposed');

    if (loading) {
        return <div className="text-center p-4 text-slate-500">Loading aliquots...</div>;
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h3 className="font-bold text-slate-900">Aliquots & Derivatives</h3>
                    <p className="text-sm text-slate-600">
                        Parent: {parentAccessionNumber} ({parentSampleType})
                    </p>
                </div>
                <button
                    onClick={() => setShowForm(!showForm)}
                    className="btn-secondary text-sm"
                >
                    {showForm ? 'Cancel' : '+ Create Aliquot'}
                </button>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-3 gap-3">
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <p className="text-xs text-green-700 font-semibold">Active</p>
                    <p className="text-2xl font-bold text-green-800">{activeAliquots.length}</p>
                </div>
                <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
                    <p className="text-xs text-orange-700 font-semibold">Used</p>
                    <p className="text-2xl font-bold text-orange-800">{usedAliquots.length}</p>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                    <p className="text-xs text-slate-700 font-semibold">Disposed</p>
                    <p className="text-2xl font-bold text-slate-800">{disposedAliquots.length}</p>
                </div>
            </div>

            {/* Create Form */}
            {showForm && (
                <form onSubmit={handleCreateAliquots} className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
                    <h4 className="font-semibold text-blue-900">Create New Aliquot(s)</h4>

                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Sample Type</label>
                            <select
                                className="input-field text-sm"
                                value={formData.type}
                                onChange={e => setFormData({ ...formData, type: e.target.value })}
                            >
                                <option>Whole Blood</option>
                                <option>Serum</option>
                                <option>Plasma</option>
                                <option>Urine</option>
                                <option>Tissue</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Number of Aliquots</label>
                            <input
                                type="number"
                                min="1"
                                max="10"
                                className="input-field text-sm"
                                value={formData.count}
                                onChange={e => setFormData({ ...formData, count: parseInt(e.target.value) || 1 })}
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Volume (optional)</label>
                            <div className="flex gap-2">
                                <input
                                    type="number"
                                    step="0.1"
                                    className="input-field text-sm flex-1"
                                    placeholder="e.g., 5"
                                    value={formData.volume}
                                    onChange={e => setFormData({ ...formData, volume: e.target.value })}
                                />
                                <select
                                    className="input-field text-sm w-20"
                                    value={formData.volumeUnit}
                                    onChange={e => setFormData({ ...formData, volumeUnit: e.target.value })}
                                >
                                    <option>mL</option>
                                    <option>µL</option>
                                </select>
                            </div>
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Container ID (optional)</label>
                            <input
                                type="text"
                                className="input-field text-sm"
                                placeholder="Barcode..."
                                value={formData.containerId}
                                onChange={e => setFormData({ ...formData, containerId: e.target.value })}
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Storage Location</label>
                            <input
                                type="text"
                                className="input-field text-sm"
                                placeholder="e.g., Freezer A"
                                value={formData.location}
                                onChange={e => setFormData({ ...formData, location: e.target.value })}
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-slate-700 mb-1">Purpose (optional)</label>
                            <input
                                type="text"
                                className="input-field text-sm"
                                placeholder="e.g., Repeat testing"
                                value={formData.purpose}
                                onChange={e => setFormData({ ...formData, purpose: e.target.value })}
                            />
                        </div>
                    </div>

                    <button type="submit" className="btn-primary w-full text-sm">
                        Create {formData.count > 1 ? `${formData.count} Aliquots` : 'Aliquot'}
                    </button>
                </form>
            )}

            {/* Aliquot List */}
            {aliquots.length === 0 ? (
                <div className="text-center p-8 bg-slate-50 border border-slate-200 rounded-lg text-slate-500">
                    No aliquots created yet.
                </div>
            ) : (
                <div className="space-y-2">
                    {aliquots.map(aliquot => (
                        <div
                            key={aliquot.id}
                            className={`border rounded-lg p-3 ${aliquot.status === 'Active'
                                    ? 'bg-white border-slate-200'
                                    : aliquot.status === 'Used'
                                        ? 'bg-orange-50 border-orange-200'
                                        : 'bg-slate-100 border-slate-300'
                                }`}
                        >
                            <div className="flex justify-between items-start">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-mono font-bold text-slate-900">{aliquot.fullIdentifier}</span>
                                        <span className={`text-xs px-2 py-0.5 rounded font-semibold ${aliquot.status === 'Active'
                                                ? 'bg-green-100 text-green-700'
                                                : aliquot.status === 'Used'
                                                    ? 'bg-orange-100 text-orange-700'
                                                    : 'bg-slate-200 text-slate-700'
                                            }`}>
                                            {aliquot.status}
                                        </span>
                                    </div>
                                    <div className="text-sm text-slate-600 mt-1 space-y-0.5">
                                        <p>Type: {aliquot.type}</p>
                                        {aliquot.volume && (
                                            <p>Volume: {aliquot.volume} {aliquot.volumeUnit}</p>
                                        )}
                                        {aliquot.location && (
                                            <p>Location: {aliquot.location}</p>
                                        )}
                                        {aliquot.containerId && (
                                            <p>Container: {aliquot.containerId}</p>
                                        )}
                                        {aliquot.purpose && (
                                            <p className="italic">Purpose: {aliquot.purpose}</p>
                                        )}
                                        <p className="text-xs text-slate-500">
                                            Created: {formatDateTime(aliquot.createdAt)} by {aliquot.createdByName}
                                        </p>
                                    </div>
                                </div>

                                {aliquot.status === 'Active' && (
                                    <div className="flex gap-2 ml-4">
                                        <button
                                            onClick={() => handleUpdateStatus(aliquot.id, 'Used')}
                                            className="text-xs px-3 py-1 bg-orange-100 hover:bg-orange-200 text-orange-700 rounded font-medium transition-colors"
                                        >
                                            Mark Used
                                        </button>
                                        <button
                                            onClick={() => handleUpdateStatus(aliquot.id, 'Disposed')}
                                            className="text-xs px-3 py-1 bg-red-100 hover:bg-red-200 text-red-700 rounded font-medium transition-colors"
                                        >
                                            Dispose
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
