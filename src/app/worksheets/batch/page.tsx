'use client';
import { useState, useEffect } from 'react';

export default function BatchEntry() {
    const [department, setDepartment] = useState('Hematology');
    const [worklist, setWorklist] = useState<any[]>([]);
    const [inputs, setInputs] = useState<Record<string, string>>({}); // orderId-testId -> value

    useEffect(() => {
        fetch(`/api/worksheets/batch?department=${department}`)
            .then(res => res.json())
            .then(data => Array.isArray(data) ? setWorklist(data) : setWorklist([]))
            .catch(() => setWorklist([]));
    }, [department]);

    const handleInputChange = (orderId: string, testId: string, val: string) => {
        setInputs(prev => ({ ...prev, [`${orderId}-${testId}`]: val }));
    };

    const cleanInputs = (orderId: string) => {
        // Remove entries for this order
        // Not strictly necessary for demo
    }

    const handleSave = async (orderId: string, testId: string) => {
        const val = inputs[`${orderId}-${testId}`];
        if (!val) return;

        // Call standard result API
        try {
            await fetch('/api/results', {
                method: 'POST',
                body: JSON.stringify({
                    orderId,
                    values: { results: { [testId]: val } },
                    status: 'Technically Validated', // Batch entry implies tech review
                    action: 'TECHNICAL_VALIDATE'
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            // Visual feedback could be added here
            alert('Saved!');
        } catch (e) {
            alert('Error saving');
        }
    };

    return (
        <div className="p-8 bg-gray-50 min-h-screen">
            <div className="flex justify-between mb-8">
                <h1 className="text-3xl font-bold">Batch Result Entry</h1>
                <select
                    value={department}
                    onChange={e => setDepartment(e.target.value)}
                    className="border p-2 rounded"
                >
                    <option>Hematology</option>
                    <option>Chemistry</option>
                    <option>Urinalysis</option>
                </select>
            </div>

            <div className="bg-white shadow rounded-lg overflow-hidden">
                <table className="w-full text-left">
                    <thead className="bg-gray-100 border-b">
                        <tr>
                            <th className="p-4">Accession</th>
                            <th className="p-4">Test</th>
                            <th className="p-4">Result</th>
                            <th className="p-4">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {worklist.map(order => (
                            order.tests.map((testId: string) => (
                                <tr key={order.orderId + testId} className="border-b hover:bg-gray-50">
                                    <td className="p-4 font-mono">{order.accessionNumber}</td>
                                    <td className="p-4"><span className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm font-bold">{testId}</span></td>
                                    <td className="p-4">
                                        <input
                                            className="border p-2 rounded w-32"
                                            placeholder="Value"
                                            value={inputs[`${order.orderId}-${testId}`] || ''}
                                            onChange={e => handleInputChange(order.orderId, testId, e.target.value)}
                                        />
                                    </td>
                                    <td className="p-4">
                                        <button
                                            onClick={() => handleSave(order.orderId, testId)}
                                            className="text-blue-600 hover:text-blue-800 font-bold"
                                        >
                                            Save
                                        </button>
                                    </td>
                                </tr>
                            ))
                        ))}
                    </tbody>
                </table>
                {worklist.length === 0 && <div className="p-8 text-center text-gray-500">No pending work for {department}</div>}
            </div>
        </div>
    );
}
