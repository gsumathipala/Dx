'use client';

import { useState, useEffect } from 'react';

export default function PatientsPage() {
    const [patients, setPatients] = useState<any[]>([]);
    const [showForm, setShowForm] = useState(false);

    async function fetchPatients() {
        try {
            const res = await fetch('/api/patients');
            const data = await res.json();
            setPatients(data);
        } catch (error) {
            console.error('Failed to fetch patients', error);
        }
    }

    useEffect(() => { fetchPatients(); }, []);

    async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);
        const data = Object.fromEntries(formData.entries());

        console.log('Submitting Patient Data:', data);

        const res = await fetch('/api/patients', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        if (res.ok) {
            e.currentTarget.reset(); // Clear form
            setShowForm(false);
            fetchPatients();
        } else {
            const err = await res.json();
            console.error('Patient creation failed:', err);
            alert(`Failed to create patient: ${err.error || 'Unknown error'}`);
        }
    }

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-lg)' }}>
                <h1>Patient Management</h1>
                <button
                    onClick={() => setShowForm(!showForm)}
                    style={{
                        backgroundColor: 'var(--primary-color)',
                        color: 'white',
                        border: 'none',
                        padding: 'var(--spacing-sm) var(--spacing-md)',
                        borderRadius: 'var(--radius-sm)'
                    }}
                >
                    {showForm ? 'Cancel' : 'Add New Patient'}
                </button>
            </div>

            {showForm && (
                <form onSubmit={handleSubmit} style={{
                    backgroundColor: 'white',
                    padding: 'var(--spacing-md)',
                    borderRadius: 'var(--radius-md)',
                    marginBottom: 'var(--spacing-lg)',
                    boxShadow: 'var(--shadow-sm)',
                    display: 'grid',
                    gap: 'var(--spacing-md)',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))'
                }}>
                    <div>
                        <label style={{ display: 'block', marginBottom: 'var(--spacing-xs)' }}>First Name</label>
                        <input
                            name="firstName"
                            required
                            style={{ width: '100%', padding: '8px', border: '1px solid var(--border-color)', borderRadius: '4px' }}
                        />
                    </div>
                    <div>
                        <label style={{ display: 'block', marginBottom: 'var(--spacing-xs)' }}>Last Name</label>
                        <input
                            name="lastName"
                            required
                            style={{ width: '100%', padding: '8px', border: '1px solid var(--border-color)', borderRadius: '4px' }}
                        />
                    </div>
                    <div>
                        <label style={{ display: 'block', marginBottom: 'var(--spacing-xs)' }}>Date of Birth</label>
                        <input
                            name="dob"
                            type="date"
                            required
                            style={{ width: '100%', padding: '8px', border: '1px solid var(--border-color)', borderRadius: '4px' }}
                        />
                    </div>
                    <div>
                        <label style={{ display: 'block', marginBottom: 'var(--spacing-xs)' }}>MRN (ID)</label>
                        <input
                            name="mrn"
                            required
                            style={{ width: '100%', padding: '8px', border: '1px solid var(--border-color)', borderRadius: '4px' }}
                        />
                    </div>
                    <div>
                        <label style={{ display: 'block', marginBottom: 'var(--spacing-xs)' }}>Gender</label>
                        <select
                            name="gender"
                            style={{ width: '100%', padding: '8px', border: '1px solid var(--border-color)', borderRadius: '4px' }}
                            defaultValue="Male"
                        >
                            <option value="Male">Male</option>
                            <option value="Female">Female</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>
                    <div style={{ gridColumn: '1 / -1' }}>
                        <button type="submit" style={{
                            backgroundColor: 'var(--secondary-color)',
                            color: 'white',
                            border: 'none',
                            padding: '8px 16px',
                            borderRadius: '4px'
                        }}>Save Patient</button>
                    </div>
                </form>
            )}

            <div style={{ backgroundColor: 'white', borderRadius: 'var(--radius-md)', overflowX: 'auto', boxShadow: 'var(--shadow-sm)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead>
                        <tr style={{ borderBottom: '2px solid var(--bg-color)' }}>
                            <th style={{ padding: '12px' }}>MRN</th>
                            <th style={{ padding: '12px' }}>Name</th>
                            <th style={{ padding: '12px' }}>DOB</th>
                            <th style={{ padding: '12px' }}>Gender</th>
                            <th style={{ padding: '12px' }}>System ID</th>
                        </tr>
                    </thead>
                    <tbody>
                        {patients.map((p: any) => (
                            <tr key={p.id} style={{ borderBottom: '1px solid var(--bg-color)' }}>
                                <td style={{ padding: '12px' }}>{p.mrn}</td>
                                <td style={{ padding: '12px' }}>
                                    <a href={`/patients/${p.id}`} style={{ color: 'var(--primary-color)', fontWeight: 'bold', textDecoration: 'none' }}>
                                        {p.lastName}, {p.firstName}
                                    </a>
                                </td>
                                <td style={{ padding: '12px' }}>{p.dob}</td>
                                <td style={{ padding: '12px' }}>{p.gender}</td>
                                <td style={{ padding: '12px', color: 'var(--text-secondary)', fontSize: '0.9em' }}>{p.id}</td>
                            </tr>
                        ))}
                        {patients.length === 0 && (
                            <tr>
                                <td colSpan={5} style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                                    No patients found. Add one to get started.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
