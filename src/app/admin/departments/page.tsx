"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Package, Building2, Microscope, FlaskConical, Activity, Plus, Power, Lock, AlertTriangle } from 'lucide-react';

export default function DepartmentsPage() {
    const [departments, setDepartments] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);
    const [newDept, setNewDept] = useState({ name: '', code: '', type: 'clinical', description: '' });
    const [user, setUser] = useState<any>(null);
    const [createError, setCreateError] = useState('');
    const [creating, setCreating] = useState(false);

    // Toggle Modal State
    const [toggleModal, setToggleModal] = useState<{ dept: any; newStatus: boolean } | null>(null);
    const [adminPassword, setAdminPassword] = useState('');
    const [toggleError, setToggleError] = useState('');
    const [toggling, setToggling] = useState(false);

    useEffect(() => {
        loadDepts();
        loadUser();
    }, []);

    const loadUser = async () => {
        const res = await fetch('/api/auth/me');
        if (res.ok) setUser(await res.json());
    };

    const loadDepts = async () => {
        // Admin page shows all departments including disabled
        const res = await fetch('/api/admin/departments?includeDisabled=true');
        if (res.ok) setDepartments(await res.json());
        setLoading(false);
    };

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        setCreateError('');
        setCreating(true);

        try {
            const res = await fetch('/api/admin/departments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(newDept)
            });

            if (res.ok) {
                setShowAdd(false);
                setNewDept({ name: '', code: '', type: 'clinical', description: '' });
                loadDepts();
            } else {
                const data = await res.json();
                setCreateError(data.error || 'Failed to create department');
            }
        } catch (err) {
            setCreateError('Failed to create department. Please try again.');
        } finally {
            setCreating(false);
        }
    };

    const handleToggle = (dept: any) => {
        if (user?.role !== 'admin') {
            alert('Only administrators can enable/disable departments.');
            return;
        }
        setToggleModal({ dept, newStatus: dept.enabled === false ? true : false });
        setAdminPassword('');
        setToggleError('');
    };

    const confirmToggle = async () => {
        if (!toggleModal) return;
        setToggling(true);
        setToggleError('');

        const res = await fetch('/api/admin/departments', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                departmentId: toggleModal.dept.id,
                enabled: toggleModal.newStatus,
                adminPassword
            })
        });

        if (res.ok) {
            setToggleModal(null);
            setAdminPassword('');
            loadDepts();
        } else {
            const data = await res.json();
            setToggleError(data.error || 'Failed to update department');
        }
        setToggling(false);
    };

    const getIcon = (type: string) => {
        switch (type) {
            case 'microbiology': return Microscope;
            case 'histopathology': return Activity;
            default: return FlaskConical;
        }
    };

    const isAdmin = user?.role === 'admin';

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Laboratory Departments</h1>
                    <p className="text-slate-500">Manage lab sections to partition users, tests, and inventory.</p>
                </div>
                <Button onClick={() => setShowAdd(!showAdd)} className="bg-primary-600">
                    <Plus className="w-4 h-4 mr-2" /> Add Department
                </Button>
            </div>

            {showAdd && (
                <Card title="New Department" className="border-l-4 border-l-primary-500">
                    <form onSubmit={handleCreate} className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="text-sm font-medium mb-1 block">Name</label>
                                <Input required value={newDept.name} onChange={e => setNewDept({ ...newDept, name: e.target.value })} placeholder="e.g. Molecular Biology" />
                            </div>
                            <div>
                                <label className="text-sm font-medium mb-1 block">Code</label>
                                <Input required value={newDept.code} onChange={e => setNewDept({ ...newDept, code: e.target.value })} placeholder="e.g. MOL" maxLength={5} />
                            </div>
                            <div>
                                <label className="text-sm font-medium mb-1 block">Type</label>
                                <select
                                    className="w-full p-2 border rounded text-sm"
                                    value={newDept.type}
                                    onChange={e => setNewDept({ ...newDept, type: e.target.value })}
                                >
                                    <option value="clinical">Clinical / General</option>
                                    <option value="microbiology">Microbiology</option>
                                    <option value="histopathology">Histopathology</option>
                                    <option value="logistics">Logistics / Support</option>
                                </select>
                            </div>
                            <div className="col-span-2">
                                <label className="text-sm font-medium mb-1 block">Description</label>
                                <Input value={newDept.description} onChange={e => setNewDept({ ...newDept, description: e.target.value })} placeholder="Brief description of functions..." />
                            </div>
                        </div>
                        {createError && (
                            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                                {createError}
                            </div>
                        )}
                        <div className="flex justify-end gap-2">
                            <Button type="button" variant="outline" onClick={() => { setShowAdd(false); setCreateError(''); }}>Cancel</Button>
                            <Button type="submit" disabled={creating}>{creating ? 'Creating...' : 'Create Lab'}</Button>
                        </div>
                    </form>
                </Card>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {departments.map(dept => {
                    const Icon = getIcon(dept.type);
                    const isEnabled = dept.enabled !== false; // Default to enabled
                    return (
                        <Card key={dept.id} className={`hover:shadow-md transition-shadow ${!isEnabled ? 'opacity-50 bg-slate-100' : ''}`}>
                            <div className="flex items-start justify-between mb-4">
                                <div className={`p-3 rounded-lg ${isEnabled ? 'bg-primary-50' : 'bg-slate-200'}`}>
                                    <Icon className={`w-6 h-6 ${isEnabled ? 'text-primary-600' : 'text-slate-400'}`} />
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-mono bg-slate-100 px-2 py-1 rounded text-slate-600">{dept.code}</span>
                                    {isAdmin && (
                                        <button
                                            onClick={() => handleToggle(dept)}
                                            className={`p-1.5 rounded-full transition-colors ${isEnabled ? 'bg-green-100 text-green-600 hover:bg-green-200' : 'bg-red-100 text-red-600 hover:bg-red-200'}`}
                                            title={isEnabled ? 'Disable Department' : 'Enable Department'}
                                        >
                                            <Power className="w-4 h-4" />
                                        </button>
                                    )}
                                </div>
                            </div>
                            <h3 className={`font-bold text-lg ${isEnabled ? 'text-slate-900' : 'text-slate-500'}`}>{dept.name}</h3>
                            <p className="text-sm text-slate-500 mt-1 mb-4 h-10">{dept.description}</p>

                            <div className="pt-4 border-t border-slate-100 flex justify-between items-center text-xs text-slate-400">
                                <span>Type: <strong className="text-slate-600 capitalize">{dept.type}</strong></span>
                                {!isEnabled && <span className="bg-red-100 text-red-600 px-2 py-0.5 rounded font-medium">DISABLED</span>}
                            </div>
                        </Card>
                    );
                })}
            </div>

            {/* Password Confirmation Modal */}
            {toggleModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md">
                        <div className="flex items-center gap-3 mb-4">
                            <div className={`p-2 rounded-full ${toggleModal.newStatus ? 'bg-green-100' : 'bg-red-100'}`}>
                                {toggleModal.newStatus ? <Power className="w-5 h-5 text-green-600" /> : <AlertTriangle className="w-5 h-5 text-red-600" />}
                            </div>
                            <div>
                                <h3 className="font-bold text-lg text-slate-900">
                                    {toggleModal.newStatus ? 'Enable' : 'Disable'} Department
                                </h3>
                                <p className="text-sm text-slate-500">{toggleModal.dept.name}</p>
                            </div>
                        </div>

                        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4">
                            <p className="text-sm text-amber-800">
                                <Lock className="w-4 h-4 inline mr-1" />
                                This action requires admin password verification.
                            </p>
                        </div>

                        <div className="mb-4">
                            <label className="text-sm font-medium mb-1 block">Admin Password</label>
                            <Input
                                type="password"
                                value={adminPassword}
                                onChange={e => setAdminPassword(e.target.value)}
                                placeholder="Enter your admin password"
                                autoFocus
                            />
                            {toggleError && (
                                <p className="text-red-600 text-sm mt-1">{toggleError}</p>
                            )}
                        </div>

                        <div className="flex justify-end gap-2">
                            <Button variant="outline" onClick={() => setToggleModal(null)}>Cancel</Button>
                            <Button
                                onClick={confirmToggle}
                                disabled={!adminPassword || toggling}
                                className={toggleModal.newStatus ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'}
                            >
                                {toggling ? 'Processing...' : (toggleModal.newStatus ? 'Enable' : 'Disable')}
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
