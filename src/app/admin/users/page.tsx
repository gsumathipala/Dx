"use client";

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';



export default function AdminUsersPage() {
    const [users, setUsers] = useState<any[]>([]);
    const [editingUser, setEditingUser] = useState<any>(null); // If set, show edit form
    const [editForm, setEditForm] = useState({ password: '', role: '', name: '', department: '' });

    // Delete flow state
    const [deletingUser, setDeletingUser] = useState<any>(null);
    const [deleteAuthPass, setDeleteAuthPass] = useState('');

    const [message, setMessage] = useState('');
    const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user', name: '', department: '' });

    const [departments, setDepartments] = useState<any[]>([]);

    const loadDeps = async () => {
        // Admin user management shows all departments including disabled
        const res = await fetch('/api/admin/departments?includeDisabled=true');
        if (res.ok) setDepartments(await res.json());
    };

    const loadUsers = async () => {
        try {
            const res = await fetch('/api/admin/users');
            const data = await res.json();
            if (Array.isArray(data)) {
                setUsers(data);
            } else {
                console.error("Users API returned non-array:", data);
                setUsers([]);
            }
        } catch (e) {
            console.error("Failed to load users", e);
            setUsers([]);
        }
    };

    React.useEffect(() => { loadUsers(); loadDeps(); }, []);

    const handleCreateUser = async (e: React.FormEvent) => {
        e.preventDefault();
        const res = await fetch('/api/admin/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newUser)
        });

        if (res.ok) {
            setMessage('User created successfully.');
            setNewUser({ username: '', password: '', role: 'user', name: '', department: '' });
            loadUsers();
        } else {
            const data = await res.json();
            setMessage('Error: ' + data.error);
        }
    };

    const initDelete = (user: any) => {
        setDeletingUser(user);
        setDeleteAuthPass('');
    };

    const confirmDelete = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!deletingUser) return;

        const res = await fetch(`/api/admin/users?id=${deletingUser.id}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: deleteAuthPass })
        });

        if (res.ok) {
            setMessage(`User ${deletingUser.username} deleted.`);
            setDeletingUser(null);
            setDeleteAuthPass('');
            loadUsers();
        } else {
            const data = await res.json();
            alert('Failed to delete: ' + (data.error || 'Unknown error'));
        }
    };

    const handleEditStart = (user: any) => {
        setEditingUser(user);
        setEditForm({ password: '', role: user.role, name: user.name, department: user.department || '' });
    };

    const handleUpdateUser = async (e: React.FormEvent) => {
        e.preventDefault();
        const updates: any = { role: editForm.role, name: editForm.name, department: editForm.department };
        if (editForm.password) updates.password = editForm.password;

        const res = await fetch('/api/admin/users', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: editingUser.id, updates })
        });

        if (res.ok) {
            setMessage('User updated');
            setEditingUser(null);
            loadUsers();
        } else {
            alert('Update failed');
        }
    };

    return (
        <div className="max-w-4xl space-y-6">
            <h1 className="text-2xl font-bold text-slate-900">User Management</h1>
            {message && (
                <div className={`p-4 rounded ${message.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                    {message}
                </div>
            )}

            {/* Edit Modal / Form Overlay */}
            {editingUser && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-full max-w-md bg-white">
                        <h2 className="text-lg font-bold mb-4">Edit User: {editingUser.username}</h2>
                        <form onSubmit={handleUpdateUser} className="space-y-4">
                            <div>
                                <label className="label">Display Name</label>
                                <input className="input-field" value={editForm.name} onChange={e => setEditForm(prev => ({ ...prev, name: e.target.value }))} />
                            </div>
                            <div>
                                <label className="label">New Password (leave blank to keep current)</label>
                                <input className="input-field" type="password" value={editForm.password} onChange={e => setEditForm(prev => ({ ...prev, password: e.target.value }))} />
                            </div>
                            <div>
                                <label className="label">Role</label>
                                <select className="input-field" value={editForm.role} onChange={e => setEditForm(prev => ({ ...prev, role: e.target.value }))}>
                                    <option value="user">User</option>
                                    <option value="admin">Admin</option>
                                    <option value="manager">Manager</option>
                                    <option value="scientist">Scientist</option>
                                    <option value="medic">Medic</option>
                                </select>
                            </div>
                            <div>
                                <label className="label">Department {editForm.role !== 'admin' ? <span className="text-red-500">*</span> : <span className="text-gray-400 text-xs">(System Wide)</span>}</label>
                                <select
                                    className={`input-field ${editForm.role === 'admin' ? 'bg-gray-100 text-gray-500' : ''}`}
                                    value={editForm.role === 'admin' ? '' : editForm.department}
                                    onChange={e => setEditForm(prev => ({ ...prev, department: e.target.value }))}
                                    required={editForm.role !== 'admin'}
                                    disabled={editForm.role === 'admin'}
                                >
                                    <option value="">{editForm.role === 'admin' ? 'No Department (System Admin)' : 'Select Department...'}</option>
                                    {departments.map(d => (
                                        <option key={d.id} value={d.name}>{d.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex gap-2 justify-end">
                                <button type="button" onClick={() => setEditingUser(null)} className="btn-secondary">Cancel</button>
                                <button type="submit" className="btn-primary">Save Changes</button>
                            </div>
                        </form>
                    </Card>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            {deletingUser && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-full max-w-sm bg-white border-red-200">
                        <div className="text-center p-2">
                            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 mb-4">
                                <span className="text-2xl">⚠️</span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900">Authorize Deletion</h3>
                            <p className="text-sm text-slate-500 mt-2">
                                You are about to permanently delete user <span className="font-bold text-slate-800">{deletingUser.username}</span>.
                            </p>
                            <p className="text-sm text-slate-600 mt-4 mb-2 font-medium">
                                Enter your password to confirm:
                            </p>
                            <form onSubmit={confirmDelete} className="space-y-4">
                                <input
                                    type="password"
                                    className="input-field text-center"
                                    autoFocus
                                    placeholder="Your Password"
                                    value={deleteAuthPass}
                                    onChange={e => setDeleteAuthPass(e.target.value)}
                                    required
                                />
                                <div className="flex gap-2 justify-center mt-4">
                                    <button type="button" onClick={() => { setDeletingUser(null); setDeleteAuthPass(''); }} className="btn-secondary w-full">Cancel</button>
                                    <button type="submit" className="bg-red-600 text-white px-4 py-2 rounded font-bold hover:bg-red-700 w-full">Confirm Delete</button>
                                </div>
                            </form>
                        </div>
                    </Card>
                </div>
            )}

            {/* List of Users */}
            <Card title="Existing Users">
                <table className="w-full text-left text-sm">
                    <thead>
                        <tr className="border-b text-slate-500">
                            <th className="py-2">Display Name</th>
                            <th className="py-2">Username</th>
                            <th className="py-2">Role</th>
                            <th className="py-2">Department</th>
                            <th className="py-2">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map(u => (
                            <tr key={u.id} className="border-b last:border-0 hover:bg-slate-50">
                                <td className="py-3 font-medium">{u.name}</td>
                                <td className="py-3">{u.username}</td>
                                <td className="py-3"><span className="px-2 py-0.5 rounded bg-slate-100 text-xs uppercase font-bold text-slate-600">{u.role}</span></td>
                                <td className="py-3 text-slate-500">{u.department || '-'}</td>
                                <td className="py-3 flex gap-2">
                                    <button onClick={() => handleEditStart(u)} className="text-blue-600 hover:underline">Edit</button>
                                    <button onClick={() => initDelete(u)} className="text-red-600 hover:underline">Delete</button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </Card>

            <Card title="Register New User">
                <form onSubmit={handleCreateUser} className="space-y-4 max-w-lg">
                    {/* ... form fields kept same ... */}
                    <div>
                        <label className="label">Display Name</label>
                        <input className="input-field" required value={newUser.name} onChange={e => setNewUser(prev => ({ ...prev, name: e.target.value }))} />
                    </div>
                    <div>
                        <label className="label">Username</label>
                        <input className="input-field" required value={newUser.username} onChange={e => setNewUser(prev => ({ ...prev, username: e.target.value }))} />
                    </div>
                    <div>
                        <label className="label">Password</label>
                        <input className="input-field" type="password" required value={newUser.password} onChange={e => setNewUser(prev => ({ ...prev, password: e.target.value }))} />
                    </div>
                    <div>
                        <label className="label">Role</label>
                        <select className="input-field" value={newUser.role} onChange={e => setNewUser(prev => ({ ...prev, role: e.target.value }))}>
                            <option value="user">User (Standard)</option>
                            <option value="admin">Admin (System Owner)</option>
                            <option value="manager">Manager (Lab Manager)</option>
                            <option value="scientist">Scientist (Operator)</option>
                            <option value="medic">Medic (Clinician)</option>
                        </select>
                    </div>
                    <div>
                        <label className="label">Department {newUser.role !== 'admin' ? <span className="text-red-500">*</span> : <span className="text-gray-400 text-xs">(System Wide)</span>}</label>
                        <select
                            className={`input-field ${newUser.role === 'admin' ? 'bg-gray-100 text-gray-500' : ''}`}
                            value={newUser.role === 'admin' ? '' : newUser.department}
                            onChange={e => setNewUser(prev => ({ ...prev, department: e.target.value }))}
                            required={newUser.role !== 'admin'}
                            disabled={newUser.role === 'admin'}
                        >
                            <option value="">{newUser.role === 'admin' ? 'No Department (System Admin)' : 'Select Department...'}</option>
                            {departments.map(d => (
                                <option key={d.id} value={d.name}>{d.name}</option>
                            ))}
                        </select>
                    </div>
                    <button type="submit" className="btn-primary">Create User</button>
                </form>
            </Card>
        </div>
    );
}
