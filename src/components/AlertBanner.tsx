"use client";

import React, { useState, useEffect } from 'react';
import { AlertCircle, Info, X, CheckCircle } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

export default function AlertBanner() {
    const { user } = useAuth();
    const [alerts, setAlerts] = useState<any[]>([]);

    useEffect(() => {
        // Poll every minute or just on load? On load is fine for now.
        fetchAlerts();
    }, [user]); // Re-fetch on login

    const fetchAlerts = async () => {
        try {
            const res = await fetch('/api/alerts');
            if (res.ok) {
                const data = await res.json();
                setAlerts(data);
            }
        } catch (err) {
            console.error('Failed to parse alerts:', err);
        }
    };

    const dismissAlert = async (id: string) => {
        // Optimistic UI update
        setAlerts(alerts.filter(a => a.id !== id));

        if (user) {
            await fetch('/api/alerts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id })
            });
        }
    };

    const AlertItem = ({ alert, onDismiss }: { alert: any, onDismiss: (id: string) => void }) => {
        useEffect(() => {
            if (alert.timeout && alert.timeout > 0) {
                const timer = setTimeout(() => {
                    onDismiss(alert.id);
                }, alert.timeout * 1000);
                return () => clearTimeout(timer);
            }
        }, [alert.id, alert.timeout, onDismiss]);

        return (
            <div
                className={`
                    w-full flex items-center justify-between px-4 py-2 text-sm font-medium
                    ${alert.type === 'warning' ? 'bg-amber-100 text-amber-900 border-b border-amber-200' : ''}
                    ${alert.type === 'error' ? 'bg-red-100 text-red-900 border-b border-red-200' : ''}
                    ${alert.type === 'info' ? 'bg-blue-50 text-blue-800 border-b border-blue-100' : ''}
                `}
            >
                <div className="flex items-center gap-2">
                    {alert.type === 'warning' && <AlertCircle className="w-4 h-4" />}
                    {alert.type === 'error' && <AlertCircle className="w-4 h-4" />}
                    {alert.type === 'info' && <Info className="w-4 h-4" />}
                    <span>{alert.message}</span>
                    {alert.timeout && <span className="text-[10px] opacity-60 ml-2">(Auto-dismiss in {alert.timeout}s)</span>}
                </div>

                <button
                    onClick={() => onDismiss(alert.id)}
                    className="p-1 hover:bg-black/5 rounded-full transition-colors"
                    title="Mark as Read"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>
        );
    };

    if (alerts.length === 0) return null;

    return (
        <div className="flex flex-col w-full">
            {alerts.map((alert) => (
                <AlertItem key={alert.id} alert={alert} onDismiss={dismissAlert} />
            ))}
        </div>
    );
}
