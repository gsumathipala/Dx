'use client';

import { useState } from 'react';
import {
    CardRoot as Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription
} from "@/components/ui/Card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, CheckCircle, Lock, Download, Upload, Activity, Archive, AlertTriangle, Database } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function BackupPage() {
    const [password, setPassword] = useState('');
    const [restorePassword, setRestorePassword] = useState('');
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    const handleBackup = async (e: React.FormEvent) => {
        e.preventDefault();
        setMessage(null);
        if (!password) {
            setMessage({ type: 'error', text: 'Password is required to encrypt the backup.' });
            return;
        }

        setLoading(true);
        try {
            const formData = new FormData();
            formData.append('password', password);

            const res = await fetch('/api/admin/backup', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) throw new Error('Backup failed');

            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `clinical-lis-backup-${new Date().toISOString().split('T')[0]}.enc`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);

            setMessage({ type: 'success', text: 'Backup downloaded successfully.' });
        } catch (err) {
            setMessage({ type: 'error', text: 'Failed to create backup.' });
        } finally {
            setLoading(false);
        }
    };

    const handleRestore = async (e: React.FormEvent) => {
        e.preventDefault();
        setMessage(null);

        if (!file || !restorePassword) {
            setMessage({ type: 'error', text: 'File and Password are required.' });
            return;
        }

        if (!confirm('WARNING: This will overwrite the current database with the backup. This action cannot be undone. Are you sure?')) {
            return;
        }

        setLoading(true);
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('password', restorePassword);

            const res = await fetch('/api/admin/restore', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Restore failed');

            setMessage({ type: 'success', text: 'System restored successfully. Please refresh the page.' });
        } catch (err: any) {
            setMessage({ type: 'error', text: err.message || 'Restore failed.' });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold text-gray-800">System Maintenance</h1>

            {message && (
                <Alert variant={message.type === 'error' ? 'destructive' : 'default'} className={message.type === 'success' ? 'bg-green-50 border-green-200' : ''}>
                    {message.type === 'error' ? <AlertCircle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4 text-green-600" />}
                    <AlertTitle>{message.type === 'error' ? 'Error' : 'Success'}</AlertTitle>
                    <AlertDescription>{message.text}</AlertDescription>
                </Alert>
            )}

            <div className="grid md:grid-cols-2 gap-6">
                {/* BACKUP CARD */}
                <Card className="border-l-4 border-l-blue-500">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Download className="h-5 w-5 text-blue-500" />
                            Create Backup
                        </CardTitle>
                        <CardDescription>
                            Download an encrypted copy of the database. You must set a password to secure the file.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleBackup} className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="backup-pass">Encryption Password</Label>
                                <div className="relative">
                                    <Lock className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-500" />
                                    <Input
                                        id="backup-pass"
                                        type="password"
                                        className="pl-9"
                                        placeholder="Enter a strong password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        required
                                    />
                                </div>
                                <p className="text-xs text-gray-500">
                                    Do not lose this password. The backup cannot be restored without it.
                                </p>
                            </div>
                            <Button type="submit" disabled={loading} className="w-full">
                                {loading ? 'Processing...' : 'Download Encrypted Backup'}
                            </Button>
                        </form>
                    </CardContent>
                </Card>

                {/* RESTORE CARD */}
                <Card className="border-l-4 border-l-red-500">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Upload className="h-5 w-5 text-red-500" />
                            Restore System
                        </CardTitle>
                        <CardDescription>
                            Restore the system from a previous backup file.
                            <br />
                            <span className="font-bold text-red-600">WARNING: This will replace current data.</span>
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleRestore} className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="restore-file">Backup File (.enc)</Label>
                                <Input
                                    id="restore-file"
                                    type="file"
                                    accept=".enc"
                                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="restore-pass">Decryption Password</Label>
                                <div className="relative">
                                    <Lock className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-500" />
                                    <Input
                                        id="restore-pass"
                                        type="password"
                                        className="pl-9"
                                        placeholder="Password used during backup"
                                        value={restorePassword}
                                        onChange={(e) => setRestorePassword(e.target.value)}
                                        required
                                    />
                                </div>
                            </div>
                            <Button type="submit" variant="destructive" disabled={loading} className="w-full">
                                {loading ? 'Restoring...' : 'Restore Database'}
                            </Button>
                        </form>
                    </CardContent>
                </Card>

                {/* DATABASE HEALTH CARD */}
                <Card className="border-l-4 border-l-green-500">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Activity className="h-5 w-5 text-green-500" />
                            Database Health
                        </CardTitle>
                        <CardDescription>
                            Optimize performance and verify data integrity.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <MaintenanceAction
                            action="OPTIMIZE"
                            label="Run Optimization (VACUUM)"
                            description="Defragments database file and reclaims space."
                            setLoading={setLoading}
                            setMessage={setMessage}
                        />
                        <div className="my-4 border-t border-slate-100"></div>
                        <MaintenanceAction
                            action="CHECK_INTEGRITY"
                            label="Check Integrity"
                            description="Verifies the database is not corrupted."
                            setLoading={setLoading}
                            setMessage={setMessage}
                        />
                    </CardContent>
                </Card>

                {/* SEED DATA CARD - NEW */}
                <Card className="border-l-4 border-l-purple-500">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Database className="h-5 w-5 text-purple-500" />
                            Populate Demo Data
                        </CardTitle>
                        <CardDescription>
                            Generate synthetic patients and results for training/demo purposes.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <MaintenanceAction
                            action="SEED_DATA"
                            label="Generate Random Records"
                            description="Adds 5 patients and associated orders/results."
                            setLoading={setLoading}
                            setMessage={setMessage}
                        />
                    </CardContent>
                </Card>

                {/* DATA RETENTION CARD */}
                <Card className="border-l-4 border-l-amber-500">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Archive className="h-5 w-5 text-amber-500" />
                            Audit Log Archiving
                        </CardTitle>
                        <CardDescription>
                            Export and delete old logs to save space.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <LogArchiveForm setLoading={setLoading} setMessage={setMessage} />
                    </CardContent>
                </Card>

                {/* DANGER ZONE: FACTORY RESET */}
                <Card className="border-l-4 border-l-red-700 md:col-span-2">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-red-700">
                            <AlertTriangle className="h-5 w-5" />
                            Danger Zone: Factory Lifecycle Reset
                        </CardTitle>
                        <CardDescription>
                            Reset the entire application to a &quot;Brand New&quot; state for a new facility.
                            <br />
                            <span className="font-bold">Erases ALL Patients, Orders, Results, and Inventory. Preserves Admin Account.</span>
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <FactoryResetAction setLoading={setLoading} setMessage={setMessage} />
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

// Sub-components for cleaner code
function MaintenanceAction({ action, label, description, setLoading, setMessage }: any) {
    const [pass, setPass] = useState('');

    const run = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);
        try {
            const res = await fetch('/api/admin/maintenance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, password: pass })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            setMessage({ type: 'success', text: data.message });
            setPass('');
        } catch (err: any) {
            setMessage({ type: 'error', text: err.message });
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={run} className="flex flex-col gap-2">
            <div className="flex justify-between items-center mb-1">
                <Label className="text-base">{label}</Label>
            </div>
            <p className="text-xs text-slate-500 mb-2">{description}</p>
            <div className="flex gap-2">
                <Input
                    type="password"
                    placeholder="Admin Password"
                    value={pass}
                    onChange={e => setPass(e.target.value)}
                    className="flex-1"
                    required
                />
                <Button type="submit" variant="outline">Run</Button>
            </div>
        </form>
    );
}

function LogArchiveForm({ setLoading, setMessage }: any) {
    const [pass, setPass] = useState('');
    const [days, setDays] = useState(90);

    const run = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);
        try {
            const res = await fetch('/api/admin/maintenance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'ARCHIVE_LOGS', password: pass, params: { retentionDays: days } })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);

            if (data.count > 0) {
                // Trigger download of JSON
                const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `audit-archive-${new Date().toISOString().split('T')[0]}.json`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
            }

            setMessage({ type: 'success', text: data.message });
            setPass('');
        } catch (err: any) {
            setMessage({ type: 'error', text: err.message });
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={run} className="space-y-4">
            <div className="space-y-2">
                <Label>Retention Policy</Label>
                <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-600">Keep logs from last</span>
                    <Input
                        type="number"
                        value={days}
                        onChange={e => setDays(parseInt(e.target.value))}
                        className="w-20 inline-block"
                        min={0}
                    />
                    <span className="text-sm text-slate-600">days.</span>
                </div>
                <p className="text-xs text-slate-500">Older logs will be downloaded/archived and deleted from DB.</p>
            </div>

            <div className="space-y-2">
                <Label>Authorization</Label>
                <Input
                    type="password"
                    placeholder="Admin Password"
                    value={pass}
                    onChange={e => setPass(e.target.value)}
                    required
                />
            </div>

            <Button type="submit" variant="outline" className="w-full">Archive & Purge Logs</Button>
        </form>
    );
}

function FactoryResetAction({ setLoading, setMessage }: any) {
    const [pass, setPass] = useState('');

    const run = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!confirm('EXTREME DANGER: You are about to ERASE ALL DATA.\n\nThis will delete all patients, orders, and results.\nOnly your Admin account will be preserved.\n\nAre you absolutely sure you want to proceed?')) {
            return;
        }

        setLoading(true);
        setMessage(null);
        try {
            const res = await fetch('/api/admin/maintenance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'FACTORY_RESET', password: pass })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            setMessage({ type: 'success', text: data.message });
            setPass('');

            // Optional: Reload page after few seconds to reflect empty state?
            setTimeout(() => window.location.reload(), 2000);

        } catch (err: any) {
            setMessage({ type: 'error', text: err.message });
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={run} className="space-y-4">
            <div className="bg-red-50 p-3 rounded border border-red-200 text-sm text-red-800">
                <strong>Warning:</strong> This action cannot be undone. It is intended for setting up a new laboratory environment.
            </div>
            <div className="space-y-2">
                <Label className="text-red-700 font-bold">Confirmation</Label>
                <Input
                    type="password"
                    placeholder="Enter Admin Password to Confirm"
                    value={pass}
                    onChange={e => setPass(e.target.value)}
                    className="border-red-300 focus:ring-red-500"
                    required
                />
            </div>
            <Button type="submit" variant="destructive" className="w-full bg-red-700 hover:bg-red-800">
                FACTORY RESET SYSTEM
            </Button>
        </form>
    );
}
