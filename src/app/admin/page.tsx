"use client";

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';

export default function AdminPage() {
    const [message, setMessage] = useState('');

    const handleBackup = () => {
        window.location.href = '/api/admin/backup';
    };

    const handleRestore = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (event) => {
            try {
                const json = JSON.parse(event.target?.result as string);

                const res = await fetch('/api/admin/restore', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(json)
                });

                if (res.ok) {
                    setMessage('System restored successfully.');
                } else {
                    setMessage('Restore failed.');
                }
            } catch (err) {
                setMessage('Invalid file format.');
            }
        };
        reader.readAsText(file);
    };

    return (
        <div className="max-w-4xl space-y-6">
            <h1 className="text-2xl font-bold text-slate-900">System Administration</h1>

            {message && (
                <div className={`p-4 rounded ${message.includes('fail') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                    {message}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <Card title="Data Backup" className="border-l-4 border-l-blue-500">
                    <p className="text-slate-600 mb-4">Download a full JSON dump of the system database (Patients, Orders, Results, Config).</p>
                    <button onClick={handleBackup} className="btn-primary">
                        ⬇️ Download Backup
                    </button>
                </Card>

                <Card title="Data Restore" className="border-l-4 border-l-red-500">
                    <p className="text-slate-600 mb-4">Upload a backup file to restore the system. <br /><strong className="text-red-600">WARNING: This will overwrite detailed current data.</strong></p>
                    <input type="file" accept=".json" onChange={handleRestore} className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
                </Card>
            </div>
        </div>
    );
}
