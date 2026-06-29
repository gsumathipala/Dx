"use client";

import React, { useState, useEffect } from 'react';
import type { Workstation, WorkstationCreate } from '@/types/workstation';
import { getWorkstationStatusColor, getWorkstationUtilization, canAcceptTest } from '@/types/workstation';
import { Card } from '@/components/ui/Card';

export default function WorkstationsPage() {
    const [workstations, setWorkstations] = useState<Workstation[]>([]);
    const [tests, setTests] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [formData, setFormData] = useState<WorkstationCreate>({
        name: '',
        type: 'Analyzer',
        department: 'Chemistry',
        supportedTests: [],
        supportedSampleTypes: [],
        maxThroughput: 20
    });

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const [workstationsRes, testsRes] = await Promise.all([
                fetch('/api/workstations'),
                fetch('/api/admin/tests')
            ]);

            if (workstationsRes.ok) setWorkstations(await workstationsRes.json());
            if (testsRes.ok) setTests(await testsRes.json());
        } catch (error) {
            console.error('Failed to load data:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();

        try {
            const res = await fetch('/api/workstations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (res.ok) {
                setFormData({
                    name: '',
                    type: 'Analyzer',
                    department: 'Chemistry',
                    supportedTests: [],
                    supportedSampleTypes: [],
                    maxThroughput: 20
                });
                setShowForm(false);
                await loadData();
            } else {
                alert('Failed to create workstation');
            }
        } catch (error) {
            console.error('Error creating workstation:', error);
            alert('Error creating workstation');
        }
    };

    const handleUpdateStatus = async (id: string, newStatus: Workstation['status']) => {
        try {
            await fetch('/api/workstations', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id, status: newStatus })
            });
            await loadData();
        } catch (error) {
            console.error('Error updating status:', error);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this workstation?')) return;

        try {
            const res = await fetch(`/api/workstations?id=${id}`, { method: 'DELETE' });
            if (res.ok) {
                await loadData();
            } else {
                alert('Failed to delete workstation');
            }
        } catch (error) {
            console.error('Error deleting workstation:', error);
        }
    };

    const toggleTestSupport = (testId: string) => {
        const current = formData.supportedTests;
        const updated = current.includes(testId)
            ? current.filter(id => id !== testId)
            : [...current, testId];
        setFormData({ ...formData, supportedTests: updated });
    };

    const toggleSampleType = (sampleType: string) => {
        const current = formData.supportedSampleTypes;
        const updated = current.includes(sampleType)
            ? current.filter(type => type !== sampleType)
            : [...current, sampleType];
        setFormData({ ...formData, supportedSampleTypes: updated });
    };

    const sampleTypes = ['Whole Blood', 'Serum', 'Plasma', 'Urine', 'Swab', 'Tissue'];

    if (loading) {
        return <div className="p-8 text-center">Loading workstations...</div>;
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Workstation Management</h1>
                    <p className="text-slate-600">Configure instruments and automated routing</p>
                </div>
                <button onClick={() => setShowForm(!showForm)} className="btn-primary">
                    {showForm ? 'Cancel' : '+ Add Workstation'}
                </button>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-4 gap-4">
                <Card className="bg-green-50 border-green-200">
                    <p className="text-sm text-green-700 font-semibold">Online</p>
                    <p className="text-3xl font-bold text-green-900">
                        {workstations.filter(w => w.status === 'Online').length}
                    </p>
                </Card>
                <Card className="bg-red-50 border-red-200">
                    <p className="text-sm text-red-700 font-semibold">Offline</p>
                    <p className="text-3xl font-bold text-red-900">
                        {workstations.filter(w => w.status === 'Offline').length}
                    </p>
                </Card>
                <Card className="bg-orange-50 border-orange-200">
                    <p className="text-sm text-orange-700 font-semibold">Maintenance</p>
                    <p className="text-3xl font-bold text-orange-900">
                        {workstations.filter(w => w.status === 'Maintenance').length}
                    </p>
                </Card>
                <Card className="bg-blue-50 border-blue-200">
                    <p className="text-sm text-blue-700 font-semibold">Total Queued</p>
                    <p className="text-3xl font-bold text-blue-900">
                        {workstations.reduce((sum, w) => sum + (w.queuedTests || 0), 0)}
                    </p>
                </Card>
            </div>

            {/* Create Form */}
            {showForm && (
                <Card className="bg-blue-50 border-blue-200">
                    <form onSubmit={handleCreate} className="space-y-4">
                        <h3 className="font-bold text-blue-900">Add New Workstation</h3>

                        <div className="grid grid-cols-3 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Name *</label>
                                <input
                                    type="text"
                                    required
                                    className="input-field"
                                    placeholder="e.g., Analyzer 1"
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
                                    <option value="Analyzer">Analyzer</option>
                                    <option value="Manual">Manual Bench</option>
                                    <option value="Microscopy">Microscopy</option>
                                    <option value="Molecular">Molecular</option>
                                    <option value="Microbiology">Microbiology</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Department *</label>
                                <select
                                    className="input-field"
                                    value={formData.department}
                                    onChange={e => setFormData({ ...formData, department: e.target.value })}
                                >
                                    <option>Chemistry</option>
                                    <option>Hematology</option>
                                    <option>Microbiology</option>
                                    <option>Immunology</option>
                                    <option>Molecular</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Max Throughput (tests/hr)</label>
                                <input
                                    type="number"
                                    min="1"
                                    className="input-field"
                                    value={formData.maxThroughput}
                                    onChange={e => setFormData({ ...formData, maxThroughput: parseInt(e.target.value) })}
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Supported Tests *</label>
                            <div className="grid grid-cols-4 gap-2">
                                {tests.map(test => (
                                    <label
                                        key={test.id}
                                        className={`flex items-center gap-2 p-2 border rounded cursor-pointer transition-colors ${formData.supportedTests.includes(test.id)
                                                ? 'bg-blue-100 border-blue-400'
                                                : 'bg-white border-slate-200 hover:bg-slate-50'
                                            }`}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={formData.supportedTests.includes(test.id)}
                                            onChange={() => toggleTestSupport(test.id)}
                                            className="rounded"
                                        />
                                        <span className="text-sm">{test.name}</span>
                                    </label>
                                ))}
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Supported Sample Types *</label>
                            <div className="flex flex-wrap gap-2">
                                {sampleTypes.map(type => (
                                    <label
                                        key={type}
                                        className={`flex items-center gap-2 px-3 py-2 border rounded cursor-pointer transition-colors ${formData.supportedSampleTypes.includes(type)
                                                ? 'bg-green-100 border-green-400'
                                                : 'bg-white border-slate-200 hover:bg-slate-50'
                                            }`}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={formData.supportedSampleTypes.includes(type)}
                                            onChange={() => toggleSampleType(type)}
                                            className="rounded"
                                        />
                                        <span className="text-sm">{type}</span>
                                    </label>
                                ))}
                            </div>
                        </div>

                        <button type="submit" className="btn-primary w-full">Create Workstation</button>
                    </form>
                </Card>
            )}

            {/* Workstations List */}
            {workstations.length === 0 ? (
                <Card className="text-center p-8 text-slate-500">
                    No workstations configured. Add your first workstation above.
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {workstations.map(workstation => {
                        const utilization = getWorkstationUtilization(workstation);
                        const statusColor = getWorkstationStatusColor(workstation.status);
                        const canAccept = canAcceptTest(workstation);

                        return (
                            <Card key={workstation.id} className="hover:shadow-lg transition-shadow">
                                <div className="space-y-3">
                                    {/* Header */}
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <h3 className="font-bold text-lg text-slate-900">{workstation.name}</h3>
                                            <p className="text-sm text-slate-600">{workstation.type} - {workstation.department}</p>
                                        </div>
                                        <select
                                            className={`text-xs px-2 py-1 rounded font-semibold border ${statusColor === 'green' ? 'bg-green-100 text-green-800 border-green-300' :
                                                    statusColor === 'red' ? 'bg-red-100 text-red-800 border-red-300' :
                                                        statusColor === 'orange' ? 'bg-orange-100 text-orange-800 border-orange-300' :
                                                            'bg-yellow-100 text-yellow-800 border-yellow-300'
                                                }`}
                                            value={workstation.status}
                                            onChange={e => handleUpdateStatus(workstation.id, e.target.value as any)}
                                        >
                                            <option value="Online">Online</option>
                                            <option value="Offline">Offline</option>
                                            <option value="Maintenance">Maintenance</option>
                                            <option value="Busy">Busy</option>
                                        </select>
                                    </div>

                                    {/* Utilization */}
                                    <div>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span className="text-slate-600">Utilization</span>
                                            <span className="font-semibold">{utilization}%</span>
                                        </div>
                                        <div className="w-full bg-slate-200 rounded-full h-2">
                                            <div
                                                className={`h-2 rounded-full transition-all ${utilization >= 90 ? 'bg-red-500' :
                                                        utilization >= 75 ? 'bg-orange-500' :
                                                            utilization >= 50 ? 'bg-yellow-500' :
                                                                'bg-green-500'
                                                    }`}
                                                style={{ width: `${utilization}%` }}
                                            ></div>
                                        </div>
                                        <p className="text-xs text-slate-500 mt-1">
                                            {workstation.currentTests}/{workstation.maxThroughput} active | {workstation.queuedTests} queued
                                        </p>
                                    </div>

                                    {/* Capabilities */}
                                    <div className="text-xs">
                                        <p className="text-slate-600 font-semibold mb-1">Tests: {workstation.supportedTests.length}</p>
                                        <p className="text-slate-600 font-semibold mb-1">
                                            Samples: {workstation.supportedSampleTypes.join(', ')}
                                        </p>
                                    </div>

                                    {/* Actions */}
                                    <div className="flex justify-end pt-2 border-t">
                                        <button
                                            onClick={() => handleDelete(workstation.id)}
                                            className="text-xs text-red-600 hover:text-red-800 font-medium"
                                        >
                                            Delete
                                        </button>
                                    </div>
                                </div>
                            </Card>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
