'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { formatDateTime } from '@/lib/utils';
import Link from 'next/link';

export default function AdminLocksPage() {
    const [locks, setLocks] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchLocks();
        const interval = setInterval(fetchLocks, 10000); // Refresh every 10s
        return () => clearInterval(interval);
    }, []);

    const fetchLocks = async () => {
        try {
            const res = await fetch('/api/locks?all=true');
            if (res.ok) {
                const data = await res.json();
                setLocks(data.locks || []);
            }
        } catch (err) {
            console.error('Failed to fetch locks:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleForceRelease = async (lock: any) => {
        if (!confirm(`Force release lock for ${lock.recordId} held by ${lock.userName}?`)) return;

        try {
            // Force release via DELETE method with query params
            const response = await fetch(`/api/locks?recordType=${lock.recordType}&recordId=${lock.recordId}&reason=AdminForceRelease`, {
                method: 'DELETE'
            });

            if (response.ok) {
                fetchLocks();
                alert('Lock released');
            } else {
                alert('Failed to release lock');
            }
        } catch (err) {
            console.error(err);
            alert('Error releasing lock');
        }
    };

    if (loading) return <div className="p-8">Loading...</div>;

    return (
        <div className="p-8">
            <h1 className="text-2xl font-bold mb-6">Active Record Locks</h1>

            {locks.length === 0 ? (
                <Card className="p-12 text-center text-slate-500">
                    <div className="text-4xl mb-4">🔓</div>
                    <p>No active locks. System is idle.</p>
                </Card>
            ) : (
                <div className="space-y-4">
                    {locks.map(lock => (
                        <Card key={lock.id} className="p-4 flex justify-between items-center">
                            <div>
                                <div className="flex items-center gap-3 mb-1">
                                    <span className="font-bold text-lg">{lock.recordId}</span>
                                    <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded uppercase font-bold">{lock.recordType}</span>
                                </div>
                                <div className="text-sm text-slate-600">
                                    Locked by <span className="font-bold text-slate-900">{lock.userName}</span> ({lock.userId})
                                </div>
                                <div className="text-xs text-slate-400 mt-1">
                                    Runnning for: {Math.floor((Date.now() - new Date(lock.checkedOutAt || lock.lockedAt).getTime()) / 1000 / 60)} mins
                                </div>
                            </div>
                            <button
                                onClick={() => handleForceRelease(lock)}
                                className="px-3 py-1 bg-red-100 text-red-700 hover:bg-red-200 rounded text-sm font-bold transition-colors"
                            >
                                Force Release
                            </button>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
