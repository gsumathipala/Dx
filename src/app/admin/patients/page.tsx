"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';

export default function PatientManagementPage() {
    const [patients, setPatients] = useState<any[]>([]);
    const [query, setQuery] = useState('');
    const [editingPatient, setEditingPatient] = useState<any>(null);
    const [editForm, setEditForm] = useState({ firstName: '', lastName: '', dob: '', gender: '', mrn: '' });
    const [message, setMessage] = useState('');

    const loadPatients = (q = '') => {
        // The API defaults to returning all if q is empty
        fetch(`/api/admin/patients?q=${q}`)
            .then(res => res.json())
            .then(data => {
                if (Array.isArray(data)) setPatients(data);
                else setPatients([]);
            });
    };

    useEffect(() => { loadPatients(); }, []);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        loadPatients(query);
    };

    const handleEditStart = (p: any) => {
        setEditingPatient(p);
        setEditForm({
            firstName: p.firstName || '',
            lastName: p.lastName || '',
            dob: p.dob || '',
            gender: p.gender || '',
            mrn: p.mrn || ''
        });
        setMessage('');
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        const res = await fetch('/api/admin/patients', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: editingPatient.id,
                updates: {
                    firstName: editForm.firstName,
                    lastName: editForm.lastName,
                    dob: editForm.dob,
                    gender: editForm.gender,
                    mrn: editForm.mrn
                }
            })
        });

        if (res.ok) {
            setMessage('Patient updated successfully.');
            setEditingPatient(null);
            loadPatients(query);
            setTimeout(() => setMessage(''), 3000);
        } else {
            setMessage('Error updating patient.');
        }
    };

    return (
        <div className="max-w-5xl space-y-6">
            <h1 className="text-2xl font-bold text-slate-900">Patient Data Management</h1>
            <p className="text-slate-500">Edit patient demographics. (Admin Only)</p>

            {message && (
                <div className={`p-4 rounded ${message.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                    {message}
                </div>
            )}

            {/* Search */}
            <Card>
                <form onSubmit={handleSearch} className="flex gap-4">
                    <input
                        className="input-field flex-1"
                        placeholder="Search by Name or MRN..."
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                    />
                    <button type="submit" className="btn-primary">Search</button>
                </form>
            </Card>

            {/* Results Table */}
            <div className="bg-white rounded shadow overflow-hidden">
                <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 border-b">
                        <tr>
                            <th className="p-4 font-bold text-slate-600">MRN</th>
                            <th className="p-4 font-bold text-slate-600">Name</th>
                            <th className="p-4 font-bold text-slate-600">DOB</th>
                            <th className="p-4 font-bold text-slate-600">Gender</th>
                            <th className="p-4 font-bold text-slate-600">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {patients.length === 0 && (
                            <tr><td colSpan={5} className="p-8 text-center text-slate-400">No patients found.</td></tr>
                        )}
                        {patients.map(p => (
                            <tr key={p.id} className="hover:bg-slate-50">
                                <td className="p-4 font-mono">{p.mrn}</td>
                                <td className="p-4 font-bold text-slate-800">{p.firstName} {p.lastName}</td>
                                <td className="p-4">{p.dob}</td>
                                <td className="p-4 capitalize">{p.gender}</td>
                                <td className="p-4">
                                    <button onClick={() => handleEditStart(p)} className="text-blue-600 font-bold hover:underline">Edit</button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Edit Modal */}
            {editingPatient && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-full max-w-lg bg-white relative">
                        <button
                            onClick={() => setEditingPatient(null)}
                            className="absolute top-4 right-4 text-slate-400 hover:text-slate-600"
                        >
                            ✕
                        </button>
                        <h2 className="text-xl font-bold mb-4">Edit Patient: {editingPatient.mrn}</h2>
                        <form onSubmit={handleSave} className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="label">First Name</label>
                                    <input className="input-field" required value={editForm.firstName} onChange={e => setEditForm({ ...editForm, firstName: e.target.value })} />
                                </div>
                                <div>
                                    <label className="label">Last Name</label>
                                    <input className="input-field" required value={editForm.lastName} onChange={e => setEditForm({ ...editForm, lastName: e.target.value })} />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="label">Date of Birth</label>
                                    <input className="input-field" type="date" required value={editForm.dob} onChange={e => setEditForm({ ...editForm, dob: e.target.value })} />
                                </div>
                                <div>
                                    <label className="label">Gender</label>
                                    <select className="input-field" value={editForm.gender} onChange={e => setEditForm({ ...editForm, gender: e.target.value })}>
                                        <option value="Male">Male</option>
                                        <option value="Female">Female</option>
                                        <option value="Other">Other</option>
                                    </select>
                                </div>
                            </div>
                            <div>
                                <label className="label">MRN / Hospital Number</label>
                                <input className="input-field" value={editForm.mrn} onChange={e => setEditForm({ ...editForm, mrn: e.target.value })} />
                            </div>

                            <div className="flex justify-end gap-3 pt-4 border-t mt-4">
                                <button type="button" onClick={() => setEditingPatient(null)} className="btn-secondary">Cancel</button>
                                <button type="submit" className="btn-primary">Save Changes</button>
                            </div>
                        </form>
                    </Card>
                </div>
            )}
        </div>
    );
}
