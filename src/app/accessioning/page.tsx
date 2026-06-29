"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { formatDate } from '@/lib/utils';
import { useAuth } from '@/context/AuthContext';

export default function AccessioningPage() {
    const { user } = useAuth();
    const router = useRouter();

    // Data Sources
    const [tests, setTests] = useState<any[]>([]);

    // UI State
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState<any[]>([]);
    const [selectedPatient, setSelectedPatient] = useState<any>(null);
    const [isNewPatient, setIsNewPatient] = useState(false);

    // Forms
    const [patientForm, setPatientForm] = useState({ firstName: '', lastName: '', dob: '', mrn: '', gender: 'Male' });
    const [selectedTestIds, setSelectedTestIds] = useState<string[]>([]);
    const [samples, setSamples] = useState<any[]>([{ type: 'Whole Blood', containerId: '', location: 'Fridge 1', condition: 'Good' }]);
    const [criteria, setCriteria] = useState<string[]>([]);

    useEffect(() => {
        if (!user) return; // Wait for auth

        // Load test definitions (Admin sees all)
        const query = user?.role === 'admin' ? '?includeDisabledDepts=true' : '';
        fetch(`/api/admin/tests${query}`)
            .then(res => res.ok ? res.json() : [])
            .then(data => setTests(data))
            .catch(() => setTests([]));

        // Load rejection criteria
        fetch('/api/admin/criteria')
            .then(res => res.ok ? res.json() : [])
            .then(data => setCriteria(data))
            .catch(() => setCriteria([]));
    }, [user]);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        const res = await fetch(`/api/patients?q=${searchQuery}`);
        if (res.ok) setSearchResults(await res.json());
    };

    const handleSelectPatient = (patient: any) => {
        setSelectedPatient(patient);
        setIsNewPatient(false);
        setSearchResults([]);
        setSearchQuery('');
    };

    const handleCreateOrder = async (e: React.FormEvent) => {
        e.preventDefault();

        if (selectedTestIds.length === 0) {
            alert('Please select at least one test.');
            return;
        }

        // Validate MRN (Issue #20)
        if (isNewPatient && !patientForm.mrn) {
            alert('Hospital Number (MRN) is required.');
            return;
        }

        // 1. Create/Update Patient if needed
        // 1. Create/Update Patient if needed
        let patientId = selectedPatient?.id;

        // If "isNewPatient" is true, it might be a NEW patient OR an EDIT of selectedPatient
        if (isNewPatient) {
            const isUpdate = !!selectedPatient?.id;
            const url = '/api/patients';
            const method = isUpdate ? 'PUT' : 'POST';
            const body = isUpdate
                ? { id: selectedPatient.id, updates: patientForm, performedBy: user?.username }
                : patientForm;

            const res = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!res.ok) {
                alert('Failed to save patient details');
                return;
            }
            const savedPatient = await res.json();
            patientId = savedPatient.id;
            setSelectedPatient(savedPatient); // Update local state
        }

        // 2. Generate Accession ID - NOW SERVER SIDE
        // Client side generation REMOVED to prevent collisions

        // 3. Create Order
        const orderPayload = {
            patientId,
            // accessionNumber: ... (Let server generate)
            testIds: selectedTestIds,
            samples, // { type, containerId, location }
            status: 'Pending',
            orderBy: user?.username
        };

        const resOrder = await fetch('/api/orders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderPayload)
        });

        if (resOrder.ok) {
            const order = await resOrder.json();
            const serverAccessionNumber = order.accessionNumber;

            // 4. Log Chain of Custody events for each sample
            for (const sample of samples) {
                const isRejected = sample.condition && sample.condition !== 'Good';
                const action = isRejected ? 'REJECT' : 'RECEIVED';

                await fetch('/api/coc', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        specimenId: sample.containerId || `${serverAccessionNumber}-${sample.type}`,
                        accessionNumber: serverAccessionNumber,
                        eventType: action, // REJECT or RECEIVED
                        performedBy: user?.username || 'unknown',
                        performedByName: user?.name || 'Unknown User',
                        location: sample.location,
                        condition: sample.condition, // Pass the specific condition (e.g. Hemolyzed)
                        notes: isRejected
                            ? `Specimen rejected at accessioning. Reason: ${sample.condition}`
                            : `Sample received during accessioning. Type: ${sample.type}`
                    })
                });
            }

            alert(`Order Created! Accession: ${serverAccessionNumber}`);
            router.push('/dashboard/tat'); // Redirect to TAT dashboard
        } else {
            alert('Failed to create order');
        }
    };

    const handleAddSample = () => {
        setSamples([...samples, { type: 'Serum', containerId: '', location: '', condition: 'Good' }]);
    };

    const handleRemoveSample = (index: number) => {
        const newSamples = [...samples];
        newSamples.splice(index, 1);
        setSamples(newSamples);
    };

    const handleSampleChange = (index: number, field: string, value: string) => {
        setSamples(prev => {
            const newSamples = [...prev];
            newSamples[index] = { ...newSamples[index], [field]: value };
            return newSamples;
        });
    };

    const toggleTest = (id: string) => {
        if (selectedTestIds.includes(id)) {
            setSelectedTestIds(selectedTestIds.filter(t => t !== id));
        } else {
            setSelectedTestIds([...selectedTestIds, id]);
        }
    };

    return (
        <div className="max-w-4xl">
            <h1 className="text-2xl font-bold mb-6">Patient Accessioning</h1>

            {/* STEP 1: PATIENT SELECTION */}
            <div className="bg-white p-6 rounded-lg shadow mb-6">
                <h2 className="text-lg font-semibold mb-4 border-b pb-2">1. Patient Details</h2>

                {!selectedPatient && !isNewPatient && (
                    <div className="space-y-4">
                        <form onSubmit={handleSearch} className="flex gap-2">
                            <input
                                type="text"
                                placeholder="Search by Name, MRN, or ID..."
                                className="flex-1 border p-2 rounded"
                                value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                            />
                            <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded">Search</button>
                        </form>

                        {searchResults.length > 0 && (
                            <ul className="border rounded divide-y">
                                {searchResults.map(p => (
                                    <li key={p.id} className="p-3 hover:bg-gray-50 flex justify-between items-center cursor-pointer" onClick={() => handleSelectPatient(p)}>
                                        <div>
                                            <span className="font-bold">{p.firstName} {p.lastName}</span>
                                            <span className="text-gray-500 text-sm ml-2">(MRN: {p.mrn} | DOB: {formatDate(p.dob)})</span>
                                        </div>
                                        <button className="text-blue-600">Select</button>
                                    </li>
                                ))}
                            </ul>
                        )}

                        <div className="text-center pt-2">
                            <span className="text-gray-500">Or </span>
                            <button onClick={() => setIsNewPatient(true)} className="text-blue-600 font-semibold hover:underline">Register New Patient</button>
                        </div>
                    </div>
                )}

                {(selectedPatient || isNewPatient) && (
                    <div>
                        <div className="flex justify-between items-start mb-4">
                            {selectedPatient && !isNewPatient ? (
                                <div className="bg-green-50 p-3 rounded border border-green-200 w-full">
                                    <div className="font-bold text-green-800 flex justify-between">
                                        <span>{selectedPatient.firstName} {selectedPatient.lastName}</span>
                                        {['admin', 'manager'].includes(user?.role || '') && (
                                            <button
                                                onClick={() => {
                                                    setPatientForm({
                                                        firstName: selectedPatient.firstName || '',
                                                        lastName: selectedPatient.lastName || '',
                                                        dob: selectedPatient.dob || '',
                                                        mrn: selectedPatient.mrn || '',
                                                        gender: selectedPatient.gender || 'Male'
                                                    });
                                                    setIsNewPatient(true);
                                                }}
                                                className="text-xs bg-white border border-green-600 text-green-700 px-2 rounded hover:bg-green-100"
                                            >
                                                ✏️ Edit
                                            </button>
                                        )}
                                    </div>
                                    <div className="text-green-700 text-sm">MRN: {selectedPatient.mrn} | DOB: {formatDate(selectedPatient.dob)} | {selectedPatient.gender}</div>
                                </div>
                            ) : (
                                <div className="w-full">
                                    {selectedPatient && (
                                        <div className="mb-3 p-2 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
                                            ✏️ Editing: {selectedPatient.firstName} {selectedPatient.lastName}
                                        </div>
                                    )}
                                    <div className="grid grid-cols-2 gap-4 w-full">
                                        <input placeholder="First Name" className="border p-2 rounded" value={patientForm.firstName} onChange={e => setPatientForm(prev => ({ ...prev, firstName: e.target.value }))} />
                                        <input placeholder="Last Name" className="border p-2 rounded" value={patientForm.lastName} onChange={e => setPatientForm(prev => ({ ...prev, lastName: e.target.value }))} />
                                        <input type="date" placeholder="DOB" className="border p-2 rounded" value={patientForm.dob} onChange={e => setPatientForm(prev => ({ ...prev, dob: e.target.value }))} />
                                        <input placeholder="MRN (Required)" className="border p-2 rounded border-red-200" required value={patientForm.mrn} onChange={e => setPatientForm(prev => ({ ...prev, mrn: e.target.value }))} />
                                        <select className="border p-2 rounded" value={patientForm.gender} onChange={e => setPatientForm(prev => ({ ...prev, gender: e.target.value }))}>
                                            <option>Male</option>
                                            <option>Female</option>
                                            <option>Other</option>
                                        </select>
                                    </div>
                                </div>
                            )}
                            <button onClick={() => { setSelectedPatient(null); setIsNewPatient(false); setPatientForm({ firstName: '', lastName: '', dob: '', mrn: '', gender: 'Male' }); }} className="text-gray-400 hover:text-red-500 ml-4 font-bold">X</button>
                        </div>
                    </div>
                )}
            </div>

            {/* STEP 2: TEST SELECTION */}
            <div className="bg-white p-6 rounded-lg shadow mb-6">
                <h2 className="text-lg font-semibold mb-4 border-b pb-2">2. Test Selection</h2>
                <div className="space-y-6">
                    {(Object.entries(tests.reduce((acc: any, test) => {
                        const dept = test.department || 'General';
                        if (!acc[dept]) acc[dept] = [];
                        acc[dept].push(test);
                        return acc;
                    }, {})) as [string, any[]][]).map(([dept, deptTests]) => (
                        <div key={dept}>
                            <h3 className="font-semibold text-gray-700 mb-2 border-b border-gray-100 pb-1">{dept}</h3>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                {deptTests.map(test => (
                                    <div
                                        key={test.id}
                                        onClick={() => toggleTest(test.id)}
                                        className={`p-3 border rounded cursor-pointer transition-colors ${selectedTestIds.includes(test.id) ? 'bg-blue-600 text-white border-blue-600' : 'hover:bg-gray-50'}`}
                                    >
                                        <div className="font-bold">{test.name}</div>
                                        <div className={`text-xs ${selectedTestIds.includes(test.id) ? 'text-blue-100' : 'text-gray-500'}`}>{test.tatHours}h TAT</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* STEP 3: SAMPLE ENTRY */}
            <div className="bg-white p-6 rounded-lg shadow mb-6">
                <div className="flex justify-between items-center mb-4 border-b pb-2">
                    <h2 className="text-lg font-semibold">3. Samples & Tracking</h2>
                    <button type="button" onClick={handleAddSample} className="text-sm bg-gray-100 px-3 py-1 rounded hover:bg-gray-200">+ Add Sample</button>
                </div>

                <div className="space-y-3">
                    {samples.map((sample, idx) => (
                        <div key={idx} className="flex gap-2 items-end">
                            <div className="flex-1">
                                <label className="text-xs text-gray-500 block">Type</label>
                                <select
                                    className="w-full border p-2 rounded"
                                    value={sample.type}
                                    onChange={e => handleSampleChange(idx, 'type', e.target.value)}
                                >
                                    <option>Whole Blood</option>
                                    <option>Serum</option>
                                    <option>Plasma</option>
                                    <option>Urine</option>
                                    <option>Swab</option>
                                </select>
                            </div>
                            <div className="flex-1">
                                <label className="text-xs text-gray-500 block">Container ID (Barcode)</label>
                                <input
                                    type="text"
                                    className="w-full border p-2 rounded"
                                    placeholder="Scan..."
                                    value={sample.containerId}
                                    onChange={e => handleSampleChange(idx, 'containerId', e.target.value)}
                                />
                            </div>
                            <div className="flex-1">
                                <label className="text-xs text-gray-500 block">Storage</label>
                                <input
                                    type="text"
                                    className="w-full border p-2 rounded"
                                    placeholder="e.g. Fridge A"
                                    value={sample.location}
                                    onChange={e => handleSampleChange(idx, 'location', e.target.value)}
                                />
                            </div>
                            <div className="flex-1">
                                <label className="text-xs text-gray-500 block">Condition</label>
                                <select
                                    className={`w-full border p-2 rounded ${sample.condition !== 'Good' ? 'bg-red-50 border-red-300 text-red-700 font-bold' : ''}`}
                                    value={sample.condition || 'Good'}
                                    onChange={e => handleSampleChange(idx, 'condition', e.target.value)}
                                >
                                    <option value="Good">Good</option>
                                    <optgroup label="Rejection Criteria">
                                        {criteria.map(c => <option key={c} value={c}>{c}</option>)}
                                    </optgroup>
                                </select>
                            </div>
                            {samples.length > 1 && (
                                <button type="button" onClick={() => handleRemoveSample(idx)} className="text-red-500 pb-2 px-2">X</button>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            <button
                onClick={handleCreateOrder}
                disabled={!selectedPatient && !isNewPatient}
                className="w-full bg-green-600 text-white font-bold py-4 rounded-lg shadow-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
                Generate Accession & Create Order
            </button>
        </div>
    );
}
