"use client";

import React, { useState, useEffect } from 'react';
import type { StorageLocation, StorageTree, StorageHierarchy } from '@/types/storage';
import { getStorageUtilization, getUtilizationColor, getStoragePathString } from '@/types/storage';
import { Card } from '@/components/ui/Card';

export default function StorageManagementPage() {
    const [tree, setTree] = useState<StorageTree | null>(null);
    const [locations, setLocations] = useState<StorageLocation[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [selectedParent, setSelectedParent] = useState<string>('');
    const [formData, setFormData] = useState({
        name: '',
        type: 'Equipment' as const,
        temperature: '',
        capacity: '',
        notes: ''
    });

    const [selectedLocation, setSelectedLocation] = useState<any>(null);
    const [contents, setContents] = useState<any[]>([]);
    const [isAssigning, setIsAssigning] = useState(false);
    const [assignId, setAssignId] = useState('');

    useEffect(() => { loadData(); }, []);

    useEffect(() => {
        if (selectedLocation) loadContents(selectedLocation.id);
    }, [selectedLocation?.id]);

    const loadContents = async (id: string) => {
        const res = await fetch(`/api/storage/contents?locationId=${id}`);
        if (res.ok) setContents(await res.json());
    };

    const handleAssign = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const res = await fetch('/api/storage/assign', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ specimenId: assignId, locationId: selectedLocation.id })
            });

            if (res.ok) {
                setAssignId('');
                setIsAssigning(false);
                loadContents(selectedLocation.id);
                loadData(); // Update counts
            } else {
                const err = await res.json();
                alert(err.error || 'Failed to assign');
            }
        } catch (error) {
            alert('Error assigning sample');
        }
    };

    const handleUnassign = async (specimenId: string) => {
        if (!confirm('Remove this sample from storage?')) return;
        try {
            const res = await fetch('/api/storage/unassign', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ specimenId })
            });

            if (res.ok) {
                loadContents(selectedLocation.id);
                loadData();
            } else {
                alert('Failed to remove sample');
            }
        } catch (error) {
            alert('Error removing sample');
        }
    };

    const loadData = async () => {
        setLoading(true);
        try {
            const [treeRes, locationsRes] = await Promise.all([
                fetch('/api/storage?hierarchical=true'),
                fetch('/api/storage')
            ]);

            if (treeRes.ok) setTree(await treeRes.json());
            if (locationsRes.ok) setLocations(await locationsRes.json());
        } catch (error) {
            console.error('Failed to load storage data:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();

        const payload = {
            name: formData.name,
            type: formData.type,
            parentId: selectedParent || undefined,
            temperature: formData.temperature ? parseFloat(formData.temperature) : undefined,
            capacity: formData.capacity ? parseInt(formData.capacity) : undefined,
            notes: formData.notes || undefined
        };

        try {
            const res = await fetch('/api/storage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                setFormData({ name: '', type: 'Equipment', temperature: '', capacity: '', notes: '' });
                setSelectedParent('');
                setShowForm(false);
                await loadData();
            } else {
                const error = await res.json();
                alert(`Failed to create location: ${error.error}`);
            }
        } catch (error) {
            console.error('Error creating location:', error);
            alert('Error creating location');
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this storage location?')) return;

        try {
            const res = await fetch(`/api/storage?id=${id}`, { method: 'DELETE' });
            if (res.ok) {
                await loadData();
            } else {
                const error = await res.json();
                alert(`Cannot delete: ${error.error}`);
            }
        } catch (error) {
            console.error('Error deleting location:', error);
            alert('Error deleting location');
        }
    };

    if (loading) {
        return <div className="p-8 text-center">Loading storage locations...</div>;
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Storage Management</h1>
                    <p className="text-slate-600">Hierarchical sample storage tracking</p>
                </div>
                <button onClick={() => setShowForm(!showForm)} className="btn-primary">
                    {showForm ? 'Cancel' : '+ Add Location'}
                </button>
            </div>

            {/* Summary Stats */}
            {tree && (
                <div className="grid grid-cols-3 gap-4">
                    <Card className="bg-blue-50 border-blue-200">
                        <p className="text-sm text-blue-700 font-semibold">Total Locations</p>
                        <p className="text-3xl font-bold text-blue-900">{tree.totalLocations}</p>
                    </Card>
                    <Card className="bg-green-50 border-green-200">
                        <p className="text-sm text-green-700 font-semibold">Samples Stored</p>
                        <p className="text-3xl font-bold text-green-900">{tree.totalSamples}</p>
                    </Card>
                    <Card className="bg-purple-50 border-purple-200">
                        <p className="text-sm text-purple-700 font-semibold">Equipment Units</p>
                        <p className="text-3xl font-bold text-purple-900">{tree.root.length}</p>
                    </Card>
                </div>
            )}

            {/* Create Form */}
            {showForm && (
                <Card className="bg-blue-50 border-blue-200">
                    <form onSubmit={handleCreate} className="space-y-4">
                        <h3 className="font-bold text-blue-900">Add Storage Location</h3>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Location Name *</label>
                                <input
                                    type="text"
                                    required
                                    className="input-field"
                                    placeholder="e.g., Freezer A"
                                    value={formData.name}
                                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Type *</label>
                                <select
                                    className="input-field"
                                    value={formData.type}
                                    onChange={e => setFormData({ ...formData, type: e.target.value as any })}
                                >
                                    <option value="Equipment">Equipment (Freezer/Fridge)</option>
                                    <option value="Shelf">Shelf</option>
                                    <option value="Rack">Rack</option>
                                    <option value="Box">Box/Position</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Parent Location</label>
                                <select
                                    className="input-field"
                                    value={selectedParent}
                                    onChange={e => setSelectedParent(e.target.value)}
                                >
                                    <option value="">-- None (Top Level) --</option>
                                    {locations.map(loc => (
                                        <option key={loc.id} value={loc.id}>
                                            {loc.name} ({loc.type})
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Temperature (°C)</label>
                                <input
                                    type="number"
                                    step="0.1"
                                    className="input-field"
                                    placeholder="e.g., -80"
                                    value={formData.temperature}
                                    onChange={e => setFormData({ ...formData, temperature: e.target.value })}
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Capacity</label>
                                <input
                                    type="number"
                                    className="input-field"
                                    placeholder="Max positions"
                                    value={formData.capacity}
                                    onChange={e => setFormData({ ...formData, capacity: e.target.value })}
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Notes</label>
                                <input
                                    type="text"
                                    className="input-field"
                                    placeholder="Additional info..."
                                    value={formData.notes}
                                    onChange={e => setFormData({ ...formData, notes: e.target.value })}
                                />
                            </div>
                        </div>

                        <button type="submit" className="btn-primary w-full">Create Location</button>
                    </form>
                </Card>
            )}

            {/* Hierarchical Tree View */}
            {tree && tree.root.length > 0 ? (
                <Card>
                    <h3 className="font-bold text-slate-900 mb-4">Storage Hierarchy</h3>
                    <div className="space-y-2">
                        {tree.root.map(node => (
                            <StorageNode key={node.location.id} node={node} onDelete={handleDelete} onSelect={setSelectedLocation} selectedId={selectedLocation?.id} />
                        ))}
                    </div>
                </Card>
            ) : (
                <Card className="text-center p-8 text-slate-500">
                    No storage locations defined. Create your first location above.
                </Card>
            )}

            {/* Location Details & Contents */}
            {selectedLocation && (
                <Card>
                    <div className="flex justify-between items-start mb-4">
                        <div>
                            <h2 className="text-xl font-bold flex items-center gap-2">
                                <span>{selectedLocation.type === 'Box' ? '📁' : '📦'}</span>
                                {selectedLocation.name}
                            </h2>
                            <p className="text-slate-500 text-sm">{selectedLocation.type} - {selectedLocation.temperature ? `${selectedLocation.temperature}°C` : 'Ambient'}</p>
                        </div>
                        <button onClick={() => setSelectedLocation(null)} className="text-slate-400 hover:text-slate-600">✕</button>
                    </div>

                    <div className="flex gap-4 mb-4">
                        <div className="p-3 bg-slate-50 rounded border flex-1">
                            <p className="text-xs text-slate-500 uppercase font-bold">Capacity</p>
                            <p className="text-lg font-mono">{selectedLocation.currentCount || 0} / {selectedLocation.capacity || '∞'}</p>
                        </div>
                        <div className="p-3 bg-slate-50 rounded border flex-1">
                            <p className="text-xs text-slate-500 uppercase font-bold">Utilization</p>
                            <p className="text-lg font-mono">{getStorageUtilization(selectedLocation)}%</p>
                        </div>
                    </div>

                    <div className="border-t pt-4">
                        <div className="flex justify-between items-center mb-2">
                            <h3 className="font-bold text-slate-700">Stored Samples</h3>
                            <button
                                onClick={() => setIsAssigning(true)}
                                className="btn-primary text-xs"
                                disabled={selectedLocation.capacity && (selectedLocation.currentCount || 0) >= selectedLocation.capacity}
                            >
                                + Add Sample
                            </button>
                        </div>

                        {isAssigning && (
                            <form onSubmit={handleAssign} className="mb-4 p-3 bg-blue-50 rounded border border-blue-100 flex gap-2 items-end">
                                <div className="flex-1">
                                    <label className="text-xs font-bold text-blue-800">Specimen ID / Accession</label>
                                    <input
                                        className="input-field text-sm"
                                        autoFocus
                                        placeholder="Scan or type ID..."
                                        value={assignId}
                                        onChange={e => setAssignId(e.target.value)}
                                    />
                                </div>
                                <button type="submit" className="btn-primary">Assign</button>
                                <button type="button" onClick={() => setIsAssigning(false)} className="btn-secondary">Cancel</button>
                            </form>
                        )}

                        <div className="max-h-64 overflow-y-auto">
                            {contents.length === 0 ? (
                                <p className="text-slate-400 italic text-sm">No samples stored here.</p>
                            ) : (
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 text-xs uppercase text-slate-500 sticky top-0">
                                        <tr>
                                            <th className="p-2 text-left">ID</th>
                                            <th className="p-2 text-left">Type</th>
                                            <th className="p-2 text-left">Date</th>
                                            <th className="p-2 text-right">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {contents.map((s, i) => (
                                            <tr key={s.id || i} className="border-b hover:bg-slate-50">
                                                <td className="p-2 font-mono font-bold">{s.id}</td>
                                                <td className="p-2">{s.type}</td>
                                                <td className="p-2 text-xs text-slate-500">{s.storageTimestamp ? new Date(s.storageTimestamp).toLocaleDateString() : '-'}</td>
                                                <td className="p-2 text-right">
                                                    <button onClick={() => handleUnassign(s.id)} className="text-red-500 hover:text-red-700 text-xs font-bold">Remove</button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                </Card>
            )}
        </div>
    );
}

interface StorageNodeProps {
    node: StorageHierarchy;
    onDelete: (id: string) => void;
    onSelect: (loc: StorageLocation) => void;
    selectedId?: string;
    level?: number;
}

function StorageNode({ node, onDelete, onSelect, selectedId, level = 0 }: StorageNodeProps) {
    const [expanded, setExpanded] = useState(level < 2); // Auto-expand first 2 levels
    const { location, children } = node;
    const utilization = getStorageUtilization(location);
    const utilizationColor = getUtilizationColor(utilization);

    const typeIcons = {
        Equipment: '🧊',
        Shelf: '📚',
        Rack: '📦',
        Box: '📁'
    };

    const typeColors = {
        Equipment: 'bg-blue-100 border-blue-300 text-blue-800',
        Shelf: 'bg-green-100 border-green-300 text-green-800',
        Rack: 'bg-purple-100 border-purple-300 text-purple-800',
        Box: 'bg-orange-100 border-orange-300 text-orange-800'
    };

    return (
        <div className="border-l-2 border-slate-200 pl-4" style={{ marginLeft: `${level * 20}px` }}>
            <div
                className={`border rounded p-3 mb-2 cursor-pointer transition-colors ${selectedId === location.id ? 'ring-2 ring-primary-500' : ''} ${typeColors[location.type]}`}
                onClick={(e) => { e.stopPropagation(); onSelect(location); }}
            >
                <div className="flex justify-between items-start">
                    <div className="flex-1">
                        <div className="flex items-center gap-2">
                            {children.length > 0 && (
                                <button
                                    onClick={() => setExpanded(!expanded)}
                                    className="text-slate-600 hover:text-slate-900"
                                >
                                    {expanded ? '▼' : '▶'}
                                </button>
                            )}
                            <span className="text-xl">{typeIcons[location.type]}</span>
                            <span className="font-bold">{location.name}</span>
                            <span className="text-xs opacity-75">({location.type})</span>
                        </div>

                        <div className="text-sm mt-1 opacity-90 flex gap-4">
                            {location.temperature !== undefined && (
                                <span>Temp: {location.temperature}°C</span>
                            )}
                            {location.capacity && (
                                <span>
                                    Capacity: {location.currentCount || 0}/{location.capacity} ({utilization}%)
                                </span>
                            )}
                            {location.notes && (
                                <span className="italic">Note: {location.notes}</span>
                            )}
                        </div>
                    </div>

                    <button
                        onClick={() => onDelete(location.id)}
                        className="text-xs px-2 py-1 bg-white/50 hover:bg-red-100 text-red-600 rounded font-medium"
                    >
                        Delete
                    </button>
                </div>
            </div>

            {expanded && children.length > 0 && (
                <div className="mt-2">
                    {children.map(child => (
                        <StorageNode key={child.location.id} node={child} onDelete={onDelete} onSelect={onSelect} selectedId={selectedId} level={level + 1} />
                    ))}
                </div>
            )}
        </div>
    );
}
