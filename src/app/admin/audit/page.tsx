"use client";

import React, { useState, useEffect } from 'react';
import { formatDateTime } from '@/lib/utils';

export default function AuditPage() {
    const [logs, setLogs] = useState<any[]>([]);

    useEffect(() => {
        fetch('/api/admin/audit')
            .then(async res => {
                if (!res.ok) {
                    throw new Error(`API Error: ${res.status}`);
                }
                return res.json();
            })
            .then(data => {
                if (Array.isArray(data)) {
                    setLogs(data);
                } else {
                    console.error("Audit API returned non-array:", data);
                    setLogs([]);
                }
            })
            .catch(e => {
                console.error("Failed to load audit logs", e);
                setLogs([]);
            });
    }, []);

    return (
        <div>
            <h1 className="text-2xl font-bold mb-6">System Audit Log</h1>
            <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Entity</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details (Diff)</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {logs.map(log => (
                            <tr key={log.id} className="hover:bg-gray-50">
                                <td className="px-6 py-4 text-sm text-gray-500">{formatDateTime(log.timestamp)}</td>
                                <td className="px-6 py-4 text-sm font-medium text-gray-900">{log.userId}</td>
                                <td className="px-6 py-4 text-sm text-gray-900">{log.action}</td>
                                <td className="px-6 py-4 text-sm text-gray-500">{log.entityType} ({log.entityId})</td>
                                <td className="px-6 py-4 text-sm text-gray-600 font-mono">{log.diff}</td>
                            </tr>
                        ))}
                        {logs.length === 0 && <tr><td colSpan={5} className="p-4 text-center">No logs found.</td></tr>}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
