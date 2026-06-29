"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Save } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function SettingsPage() {
    const [settings, setSettings] = useState({
        institutionName: '',
        tagline: '',
        contactEmail: '',
        currencySymbol: '$',
        smtpHost: '',
        smtpPort: '',
        smtpUser: '',
        smtpPass: '',
        themeColor: 'blue',
        themeMode: 'light'
    });
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    useEffect(() => { loadSettings(); }, []);

    // Instant Preview: Apply theme classes immediately to body
    useEffect(() => {
        if (!settings.themeColor) return;

        // Remove existing theme/mode classes (use Array.from to avoid mutation issues)
        const classesToRemove = Array.from(document.body.classList).filter(
            cls => cls.startsWith('theme-') || cls.startsWith('mode-')
        );
        classesToRemove.forEach(cls => document.body.classList.remove(cls));

        // Add new theme class
        document.body.classList.add(`theme-${settings.themeColor}`);

        // Add dark mode class only if dark is selected
        if (settings.themeMode === 'dark') {
            document.body.classList.add('mode-dark');
        }
        // No else needed - we already removed mode-dark above
    }, [settings.themeColor, settings.themeMode]);

    const loadSettings = async () => {
        const res = await fetch('/api/admin/settings');
        if (res.ok) setSettings(await res.json());
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);
        try {
            const res = await fetch('/api/admin/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            if (res.ok) {
                setMessage({ type: 'success', text: 'System configuration updated. Reloading...' });
                // Force full reload to ensure server-side layout picks up changes
                setTimeout(() => window.location.reload(), 1000);
            } else {
                setMessage({ type: 'error', text: 'Failed to update settings.' });
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto space-y-6">
            <h1 className="text-3xl font-bold text-slate-900">System Configuration</h1>
            <p className="text-slate-500">Customize the identity of the Laboratory System.</p>

            {message && (
                <Alert className={message.type === 'success' ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50'}>
                    <AlertTitle>{message.type === 'success' ? 'Success' : 'Error'}</AlertTitle>
                    <AlertDescription>{message.text}</AlertDescription>
                </Alert>
            )}

            <Card className="border-t-4 border-t-primary-600">
                <form onSubmit={handleSave} className="space-y-6">
                    <div className="space-y-2">
                        <Label>Institution / Laboratory Name</Label>
                        <Input
                            value={settings.institutionName}
                            onChange={e => setSettings({ ...settings, institutionName: e.target.value })}
                            placeholder="e.g. City General Hospital Lab"
                        />
                        <p className="text-xs text-slate-500">Displayed on the Welcome Screen and Report Headers.</p>
                    </div>

                    <div className="space-y-2">
                        <Label>System Tagline / Welcome Phrase</Label>
                        <Input
                            value={settings.tagline}
                            onChange={e => setSettings({ ...settings, tagline: e.target.value })}
                            placeholder="e.g. Precision Diagnostics"
                        />
                        <p className="text-xs text-slate-500">A short phrase displayed below the title on the home page.</p>
                    </div>

                    <div className="space-y-2">
                        <Label>Contact Email</Label>
                        <Input
                            value={settings.contactEmail}
                            onChange={e => setSettings({ ...settings, contactEmail: e.target.value })}
                            placeholder="admin@lab.local"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Currency Symbol</Label>
                        <div className="flex gap-2">
                            <select
                                className="border rounded p-2 bg-white"
                                value={settings.currencySymbol || '$'}
                                onChange={e => setSettings({ ...settings, currencySymbol: e.target.value })}
                            >
                                <option value="$">Dollar ($)</option>
                                <option value="€">Euro (€)</option>
                                <option value="£">Pound (£)</option>
                                <option value="₹">Rupee (₹)</option>
                                <option value="¥">Yen (¥)</option>
                                <option value="custom">Custom</option>
                            </select>
                            {settings.currencySymbol === 'custom' && (
                                <Input
                                    placeholder="Enter Symbol"
                                    value=""
                                    onChange={e => setSettings({ ...settings, currencySymbol: e.target.value })}
                                    className="w-24"
                                />
                            )}
                        </div>
                        <p className="text-xs text-slate-500">Global currency unit for billing and financials.</p>
                    </div>

                    <div className="pt-6 border-t border-slate-100">
                        <h3 className="text-lg font-bold text-slate-800 mb-4">Email Service (SMTP)</h3>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>SMTP Host</Label>
                                <Input
                                    placeholder="smtp.gmail.com"
                                    value={settings.smtpHost || ''}
                                    onChange={e => setSettings({ ...settings, smtpHost: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Port</Label>
                                <Input
                                    placeholder="587"
                                    value={settings.smtpPort || ''}
                                    onChange={e => setSettings({ ...settings, smtpPort: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Username / Email</Label>
                                <Input
                                    placeholder="lab@hospital.org"
                                    value={settings.smtpUser || ''}
                                    onChange={e => setSettings({ ...settings, smtpUser: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Password / App Key</Label>
                                <Input
                                    type="password"
                                    placeholder="••••••••"
                                    value={settings.smtpPass || ''}
                                    onChange={e => setSettings({ ...settings, smtpPass: e.target.value })}
                                />
                            </div>
                        </div>
                        <p className="text-xs text-slate-500 mt-2">
                            Use a dedicated App Password if using Gmail/Outlook. Standard config uses TLS on port 587.
                        </p>
                    </div>

                    <div className="pt-6 border-t border-slate-100">
                        <h3 className="text-lg font-bold text-slate-800 mb-4">Branding & Appearance</h3>
                        <div className="grid grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <Label>Primary Color Scheme</Label>
                                <select
                                    className="w-full p-2 border rounded bg-white"
                                    value={settings.themeColor || 'blue'}
                                    onChange={e => setSettings({ ...settings, themeColor: e.target.value })}
                                >
                                    <option value="blue">Clinical Blue (Default)</option>
                                    <option value="emerald">Bio-Emerald (Surgical)</option>
                                    <option value="rose">Hematology Crimson</option>
                                    <option value="indigo">Deep Indigo</option>
                                    <option value="contrast">High Contrast (Accessibility)</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <Label>Interface Mode</Label>
                                <div className="flex bg-slate-100 p-1 rounded-lg">
                                    <button
                                        type="button"
                                        onClick={() => setSettings({ ...settings, themeMode: 'light' })}
                                        className={`flex-1 py-1 text-sm font-medium rounded-md transition-all ${(!settings.themeMode || settings.themeMode === 'light') ? 'bg-white shadow text-slate-900' : 'text-slate-500'}`}
                                    >
                                        ☀ Light
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setSettings({ ...settings, themeMode: 'dark' })}
                                        className={`flex-1 py-1 text-sm font-medium rounded-md transition-all ${settings.themeMode === 'dark' ? 'bg-slate-800 shadow text-white' : 'text-slate-500'}`}
                                    >
                                        🌙 Dark
                                    </button>
                                </div>
                            </div>
                        </div>
                        <p className="text-xs text-slate-500 mt-2">
                            Dark mode is useful for microscopy work. Changes apply system-wide after refresh.
                        </p>
                    </div>

                    <Button type="submit" disabled={loading} className="w-full">
                        <Save className="w-4 h-4 mr-2" />
                        Save Configuration
                    </Button>
                </form>
            </Card>

            <div className="bg-slate-100 p-6 rounded-lg text-center opacity-75">
                <h3 className="text-lg font-bold text-slate-900 mb-1">Preview:</h3>
                <h1 className="text-2xl font-bold text-primary-700">{settings.institutionName || 'Dx Lab'}</h1>
                <p className="text-slate-600 italic">&quot;{settings.tagline || 'Excellence in Diagnostics'}&quot;</p>
            </div>
        </div>
    );
}
