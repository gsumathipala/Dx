"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Thermometer, Wrench, Plus, Trash2, Save, Activity, Settings, Pencil } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

export default function EquipmentPage() {
    const [equipment, setEquipment] = useState<any[]>([]);
    const [selectedId, setSelectedId] = useState<string>('');
    const [logs, setLogs] = useState<any[]>([]);
    const { user } = useAuth();
    const userRole = user?.role || 'tech';

    // Modals
    const [showAddEq, setShowAddEq] = useState(false);
    const [newEq, setNewEq] = useState({ name: '', type: 'Temperature', rangeMin: '', rangeMax: '', unit: 'C', department: 'General' });

    const [showEditEq, setShowEditEq] = useState(false);
    const [editEqData, setEditEqData] = useState({ id: '', name: '', type: '', rangeMin: '', rangeMax: '', unit: '', department: '' });

    const [showLog, setShowLog] = useState(false);
    const [newLog, setNewLog] = useState({ value: '', note: '' });

    const loadEquipment = async () => {
        const res = await fetch('/api/equipment?type=all');
        const data = await res.json();
        setEquipment(data);
        if (data.length > 0 && !selectedId) setSelectedId(data[0].id);
    };

    const loadLogs = async (id: string) => {
        const res = await fetch(`/api/equipment?type=logs&equipmentId=${id}`);
        const data = await res.json();
        setLogs(data);
    };

    useEffect(() => {
        loadEquipment();
    }, []);

    useEffect(() => {
        if (selectedId) loadLogs(selectedId);
    }, [selectedId]);

    const handleCreateEq = async () => {
        if (!newEq.name) return;
        await fetch('/api/equipment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'create_equipment', data: newEq })
        });
        setNewEq({ name: '', type: 'Temperature', rangeMin: '', rangeMax: '', unit: 'C', department: 'General' });
        setShowAddEq(false);
        loadEquipment();
    };

    const handleDeleteEq = async (id: string) => {
        if (!confirm('Remove this equipment and all its logs?')) return;
        await fetch('/api/equipment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'delete_equipment', data: { id } })
        });
        setSelectedId('');
        loadEquipment();
    };

    const handleUpdateEq = async () => {
        await fetch('/api/equipment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'update_equipment', data: editEqData })
        });
        setShowEditEq(false);
        loadEquipment();
    };

    const openEditEq = () => {
        if (!selectedEq) return;
        setEditEqData({
            id: selectedEq.id,
            name: selectedEq.name,
            type: selectedEq.type,
            rangeMin: selectedEq.rangeMin,
            rangeMax: selectedEq.rangeMax,
            unit: selectedEq.unit,
            department: selectedEq.department
        });
        setShowEditEq(true);
    };

    const handleLogValue = async () => {
        if (!newLog.value) return;
        await fetch('/api/equipment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'log_value',
                data: {
                    equipmentId: selectedId,
                    value: parseFloat(newLog.value),
                    note: newLog.note,
                    userId: userRole // tracking who logged
                }
            })
        });
        setNewLog({ value: '', note: '' });
        setShowLog(false);
        loadLogs(selectedId);
    };

    const selectedEq = equipment.find(e => e.id === selectedId);
    const canManage = ['admin', 'manager'].includes(userRole);

    // Chart Data
    const chartData = logs.map(l => ({
        timestamp: new Date(l.timestamp).toLocaleDateString() + ' ' + new Date(l.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        value: l.value
    })).reverse();

    return (
        <div className="h-[calc(100vh-100px)] flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                        <Wrench className="h-6 w-6 text-indigo-600" />
                        Equipment Maintenance
                    </h1>
                    <p className="text-slate-500">Track logs and monitor status</p>
                </div>
                {canManage && (
                    <Button onClick={() => setShowAddEq(true)}>
                        <Plus className="w-4 h-4 mr-2" /> Add Equipment
                    </Button>
                )}
            </div>

            <div className="flex flex-1 gap-6 overflow-hidden">
                {/* Sidebar */}
                <Card className="w-64 flex flex-col overflow-hidden">
                    <div className="p-4 bg-slate-50 border-b font-bold text-slate-700">Equipment List</div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                        {equipment.length === 0 && <div className="text-sm text-slate-400 p-2 italic">No equipment defined.</div>}
                        {equipment.map(eq => (
                            <div
                                key={eq.id}
                                onClick={() => setSelectedId(eq.id)}
                                className={`p-3 rounded-md cursor-pointer text-sm transition-colors ${selectedId === eq.id ? 'bg-indigo-50 text-indigo-700 font-bold border border-indigo-200' : 'hover:bg-slate-100 text-slate-600'}`}
                            >
                                <div className="flex items-center gap-2">
                                    {eq.type === 'Temperature' ? <Thermometer className="w-4 h-4" /> : <Settings className="w-4 h-4" />}
                                    {eq.name}
                                </div>
                                <div className="text-xs font-normal opacity-75 ml-6">{eq.department}</div>
                            </div>
                        ))}
                    </div>
                </Card>

                {/* Main */}
                <div className="flex-1 flex flex-col gap-6 overflow-hidden">
                    {selectedEq ? (
                        <div className="flex-1 flex flex-col overflow-hidden space-y-4">
                            {/* Header Card */}
                            <Card className="p-4 flex justify-between items-center bg-white">
                                <div>
                                    <h2 className="text-xl font-bold flex items-center gap-2">
                                        {selectedEq.name}
                                        <span className="text-sm font-normal px-2 py-0.5 bg-slate-100 rounded text-slate-500">{selectedEq.type}</span>
                                    </h2>
                                    <div className="text-sm text-slate-500 mt-1">
                                        Acceptable Range: <strong>{selectedEq.rangeMin}</strong> to <strong>{selectedEq.rangeMax} {selectedEq.unit}</strong>
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <Button onClick={() => setShowLog(true)}>
                                        <Activity className="w-4 h-4 mr-2" /> Log Status
                                    </Button>
                                    {canManage && (
                                        <>
                                            <Button variant="outline" onClick={openEditEq}>
                                                <Pencil className="w-4 h-4" />
                                            </Button>
                                            <Button variant="destructive" onClick={() => handleDeleteEq(selectedEq.id)}>
                                                <Trash2 className="w-4 h-4" />
                                            </Button>
                                        </>
                                    )}
                                </div>
                            </Card>

                            {/* Chart */}
                            <Card className="flex-1 p-4 min-h-[300px]">
                                <h3 className="font-bold text-slate-700 mb-2">Trend Analysis</h3>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis dataKey="timestamp" stroke="#64748b" fontSize={11} tickFormatter={(v) => v.split(' ')[0]} />
                                        <YAxis domain={['auto', 'auto']} stroke="#64748b" fontSize={12} />
                                        <Tooltip />
                                        {selectedEq.rangeMax && <ReferenceLine y={parseFloat(selectedEq.rangeMax)} stroke="#ef4444" strokeDasharray="3 3" label="Max" />}
                                        {selectedEq.rangeMin && <ReferenceLine y={parseFloat(selectedEq.rangeMin)} stroke="#ef4444" strokeDasharray="3 3" label="Min" />}
                                        <Line type="monotone" dataKey="value" stroke="#4f46e5" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </Card>

                            {/* Recent Logs Table */}
                            <Card className="h-64 flex flex-col overflow-hidden">
                                <div className="p-3 bg-slate-50 border-b font-bold text-sm">Recent Logs</div>
                                <div className="overflow-y-auto">
                                    <table className="w-full text-sm text-left">
                                        <thead className="text-xs text-slate-500 bg-slate-50 uppercase sticky top-0">
                                            <tr>
                                                <th className="px-4 py-2">Timestamp</th>
                                                <th className="px-4 py-2">Value ({selectedEq.unit})</th>
                                                <th className="px-4 py-2">Note</th>
                                                <th className="px-4 py-2">User</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {logs.map(log => (
                                                <tr key={log.id} className="border-b hover:bg-slate-50">
                                                    <td className="px-4 py-2">{new Date(log.timestamp).toLocaleString()}</td>
                                                    <td className={`px-4 py-2 font-bold ${(selectedEq.rangeMin && log.value < selectedEq.rangeMin) || (selectedEq.rangeMax && log.value > selectedEq.rangeMax)
                                                        ? 'text-red-600' : 'text-slate-700'
                                                        }`}>
                                                        {log.value}
                                                    </td>
                                                    <td className="px-4 py-2 text-slate-500">{log.note || '-'}</td>
                                                    <td className="px-4 py-2 text-slate-500">{log.userId}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </Card>
                        </div>
                    ) : (
                        <div className="flex-1 flex items-center justify-center text-slate-400 italic">
                            Select an instrument to view logs...
                        </div>
                    )}
                </div>
            </div>

            {/* Add Equipment Modal */}
            {showAddEq && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-96 p-6 bg-white shadow-xl space-y-4">
                        <h3 className="text-lg font-bold">Add Equipment</h3>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Name</label>
                            <Input value={newEq.name} onChange={e => setNewEq({ ...newEq, name: e.target.value })} placeholder="e.g. Main Freezer" />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Type</label>
                                <select
                                    className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    value={newEq.type}
                                    onChange={e => setNewEq({ ...newEq, type: e.target.value })}
                                >
                                    <option value="Temperature">Temperature</option>
                                    <option value="Maintenance">Maintenance</option>
                                    <option value="Other">Other</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Department</label>
                                <Input value={newEq.department} onChange={e => setNewEq({ ...newEq, department: e.target.value })} />
                            </div>
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Min</label>
                                <Input value={newEq.rangeMin} onChange={e => setNewEq({ ...newEq, rangeMin: e.target.value })} type="number" />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Max</label>
                                <Input value={newEq.rangeMax} onChange={e => setNewEq({ ...newEq, rangeMax: e.target.value })} type="number" />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Unit</label>
                                <Input value={newEq.unit} onChange={e => setNewEq({ ...newEq, unit: e.target.value })} />
                            </div>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                            <Button variant="outline" onClick={() => setShowAddEq(false)}>Cancel</Button>
                            <Button onClick={handleCreateEq}>Create</Button>
                        </div>
                    </Card>
                </div>
            )}

            {/* Edit Equipment Modal */}
            {showEditEq && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-96 p-6 bg-white shadow-xl space-y-4">
                        <h3 className="text-lg font-bold">Edit Equipment</h3>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Name</label>
                            <Input value={editEqData.name} onChange={e => setEditEqData({ ...editEqData, name: e.target.value })} />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Type</label>
                                <select
                                    className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    value={editEqData.type}
                                    onChange={e => setEditEqData({ ...editEqData, type: e.target.value })}
                                >
                                    <option value="Temperature">Temperature</option>
                                    <option value="Maintenance">Maintenance</option>
                                    <option value="Other">Other</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Department</label>
                                <Input value={editEqData.department} onChange={e => setEditEqData({ ...editEqData, department: e.target.value })} />
                            </div>
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Min</label>
                                <Input value={editEqData.rangeMin} onChange={e => setEditEqData({ ...editEqData, rangeMin: e.target.value })} type="number" />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Max</label>
                                <Input value={editEqData.rangeMax} onChange={e => setEditEqData({ ...editEqData, rangeMax: e.target.value })} type="number" />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Unit</label>
                                <Input value={editEqData.unit} onChange={e => setEditEqData({ ...editEqData, unit: e.target.value })} />
                            </div>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                            <Button variant="outline" onClick={() => setShowEditEq(false)}>Cancel</Button>
                            <Button onClick={handleUpdateEq}>Save Changes</Button>
                        </div>
                    </Card>
                </div>
            )}

            {/* Log Value Modal */}
            {showLog && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-80 p-6 bg-white shadow-xl space-y-4">
                        <h3 className="text-lg font-bold">Log Status</h3>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Current Value ({selectedEq?.unit})</label>
                            <Input value={newLog.value} onChange={e => setNewLog({ ...newLog, value: e.target.value })} type="number" autoFocus />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Note (Optional)</label>
                            <Input value={newLog.note} onChange={e => setNewLog({ ...newLog, note: e.target.value })} />
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                            <Button variant="outline" onClick={() => setShowLog(false)}>Cancel</Button>
                            <Button onClick={handleLogValue}>Save Log</Button>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
}
