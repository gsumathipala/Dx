'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';

interface Department {
    id: string;
    name: string;
    code: string;
    enabled?: boolean;
}

interface Queue {
    id: string;
    name: string;
    description: string;
    department: string;
    allowedRoles: string[];
    createdBy: string;
    createdAt: string;
}

export default function QueueManagementPage() {
    const { user } = useAuth();
    const router = useRouter();
    const [queues, setQueues] = useState<Queue[]>([]);
    const [departments, setDepartments] = useState<Department[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        department: '',
        allowedRoles: ['admin', 'manager'] as string[]
    });
    const [error, setError] = useState('');

    const AVAILABLE_ROLES = ['scientist', 'medic', 'clerk'];

    // Check authorization
    useEffect(() => {
        if (!user) return;
        if (!['admin', 'manager'].includes(user.role)) {
            router.push('/');
        }
    }, [user, router]);

    useEffect(() => {
        fetchQueues();
        fetchDepartments();
    }, []);

    const fetchQueues = async () => {
        try {
            const res = await fetch('/api/queues');
            if (res.ok) {
                const data = await res.json();
                setQueues(data);
            }
        } catch (err) {
            console.error('Failed to fetch queues:', err);
        } finally {
            setLoading(false);
        }
    };

    const fetchDepartments = async () => {
        try {
            const res = await fetch('/api/admin/departments');
            if (res.ok) {
                const data = await res.json();
                setDepartments(Array.isArray(data) ? data.filter((d: Department) => d.enabled !== false) : []);
            }
        } catch (err) {
            console.error('Failed to fetch departments:', err);
        }
    };

    const toggleRole = (role: string) => {
        setFormData(prev => {
            const roles = prev.allowedRoles.includes(role)
                ? prev.allowedRoles.filter(r => r !== role)
                : [...prev.allowedRoles, role];
            return { ...prev, allowedRoles: roles };
        });
    };

    const handleCreate = async () => {
        if (!formData.name.trim()) {
            setError('Queue name is required');
            return;
        }
        if (!formData.department.trim()) {
            setError('Department is required');
            return;
        }

        try {
            const res = await fetch('/api/queues', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData),
            });

            if (res.ok) {
                setFormData({ name: '', description: '', department: '', allowedRoles: ['admin', 'manager'] });
                setShowCreateForm(false);
                setError('');
                fetchQueues();
            } else {
                const data = await res.json();
                setError(data.error || 'Failed to create queue');
            }
        } catch (err) {
            setError('Failed to create queue');
        }
    };

    const handleUpdate = async (id: string, updates: Partial<Queue>) => {
        try {
            const res = await fetch('/api/queues', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id, ...updates }),
            });

            if (res.ok) {
                setEditingId(null);
                fetchQueues();
            } else {
                const data = await res.json();
                setError(data.error || 'Failed to update queue');
            }
        } catch (err) {
            setError('Failed to update queue');
        }
    };

    const handleDelete = async (id: string, name: string) => {
        if (!confirm(`Are you sure you want to delete the queue "${name}"? This action cannot be undone.`)) {
            return;
        }

        try {
            const res = await fetch(`/api/queues?id=${id}`, {
                method: 'DELETE',
            });

            if (res.ok) {
                fetchQueues();
            } else {
                const data = await res.json();
                alert(data.error || 'Failed to delete queue');
            }
        } catch (err) {
            alert('Failed to delete queue');
        }
    };

    if (loading) {
        return (
            <div className="p-8">
                <p className="text-slate-400">Loading...</p>
            </div>
        );
    }

    return (
        <div className="p-8">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">Authorization Queues</h1>
                <button
                    onClick={() => setShowCreateForm(!showCreateForm)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                    {showCreateForm ? 'Cancel' : '+ Create Queue'}
                </button>
            </div>

            {error && (
                <div className="mb-4 p-4 bg-red-500/10 border border-red-500 rounded-lg text-red-500">
                    {error}
                </div>
            )}

            {showCreateForm && (
                <div className="mb-6 p-6 bg-slate-800 rounded-lg border border-slate-700">
                    <h3 className="text-lg font-semibold mb-4">Create New Queue</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium mb-2">Queue Name *</label>
                                <input
                                    type="text"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                                    placeholder="e.g., Hematology Review"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-2">Description</label>
                                <textarea
                                    value={formData.description}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                                    rows={3}
                                    placeholder="Optional description"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-2">Department / Lab *</label>
                                <select
                                    value={formData.department}
                                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                                    className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                                >
                                    <option value="">Select a department...</option>
                                    {departments.map(dept => (
                                        <option key={dept.id} value={dept.name}>{dept.name} ({dept.code})</option>
                                    ))}
                                </select>
                                {departments.length === 0 && (
                                    <p className="mt-2 text-sm text-amber-400">
                                        No departments found. Create departments in Admin → Departments first.
                                    </p>
                                )}
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2">Allowed Roles (Access Control)</label>
                            <div className="space-y-2 bg-slate-900 p-4 rounded-lg border border-slate-700">
                                <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
                                    <span>Admins & Managers always have access.</span>
                                </div>
                                {AVAILABLE_ROLES.map(role => (
                                    <label key={role} className="flex items-center gap-2 cursor-pointer hover:bg-slate-800 p-2 rounded">
                                        <input
                                            type="checkbox"
                                            checked={formData.allowedRoles.includes(role)}
                                            onChange={() => toggleRole(role)}
                                            className="w-4 h-4 rounded border-slate-600 bg-slate-700"
                                        />
                                        <span className="capitalize">{role}</span>
                                    </label>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="mt-6 flex justify-end">
                        <button
                            onClick={handleCreate}
                            className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                        >
                            Create Queue
                        </button>
                    </div>
                </div>
            )}

            <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
                <table className="w-full">
                    <thead className="bg-slate-900/50">
                        <tr>
                            <th className="text-left px-6 py-4 text-sm font-semibold">Queue Name</th>
                            <th className="text-left px-6 py-4 text-sm font-semibold">Department</th>
                            <th className="text-left px-6 py-4 text-sm font-semibold">Allowed Roles</th>
                            <th className="text-left px-6 py-4 text-sm font-semibold">Description</th>
                            <th className="text-left px-6 py-4 text-sm font-semibold">Created By</th>
                            <th className="text-right px-6 py-4 text-sm font-semibold">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                        {queues.length === 0 ? (
                            <tr>
                                <td colSpan={6} className="px-6 py-8 text-center text-slate-400">
                                    No queues found. Create your first queue above.
                                </td>
                            </tr>
                        ) : (
                            queues.map((queue) => (
                                <tr key={queue.id} className="hover:bg-slate-700/30 transition-colors">
                                    <td className="px-6 py-4">
                                        {editingId === queue.id ? (
                                            <input
                                                type="text"
                                                defaultValue={queue.name}
                                                onBlur={(e) => {
                                                    if (e.target.value !== queue.name) {
                                                        handleUpdate(queue.id, { name: e.target.value });
                                                    } else {
                                                        setEditingId(null);
                                                    }
                                                }}
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter') {
                                                        handleUpdate(queue.id, { name: e.currentTarget.value });
                                                    } else if (e.key === 'Escape') {
                                                        setEditingId(null);
                                                    }
                                                }}
                                                autoFocus
                                                className="px-2 py-1 bg-slate-900 border border-blue-500 rounded outline-none"
                                            />
                                        ) : (
                                            <span className="font-medium">{queue.name}</span>
                                        )}
                                    </td>
                                    <td className="px-6 py-4 text-sm">
                                        <span className="px-2 py-1 rounded bg-purple-600/20 text-purple-300 text-xs font-medium">
                                            {queue.department || <span className="text-slate-500 italic">None</span>}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-sm">
                                        <div className="flex flex-wrap gap-1">
                                            {(queue.allowedRoles || []).map(role => (
                                                <span key={role} className="px-2 py-0.5 rounded text-xs font-bold bg-slate-700 text-slate-300 capitalize">
                                                    {role}
                                                </span>
                                            ))}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-slate-300 text-sm">
                                        {queue.description || <span className="text-slate-500 italic">No description</span>}
                                    </td>
                                    <td className="px-6 py-4 text-sm text-slate-400">{queue.createdBy}</td>
                                    <td className="px-6 py-4 text-right">
                                        <button
                                            onClick={() => setEditingId(queue.id)}
                                            className="px-3 py-1 text-sm text-blue-400 hover:text-blue-300 mr-2"
                                        >
                                            Edit Name
                                        </button>
                                        <button
                                            onClick={() => handleDelete(queue.id, queue.name)}
                                            className="px-3 py-1 text-sm text-red-400 hover:text-red-300"
                                        >
                                            Delete
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
