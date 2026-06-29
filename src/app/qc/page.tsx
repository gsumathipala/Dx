"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer } from 'recharts';
import { Activity, Settings, Plus, TestTube, Save, AlertCircle, Trash2, Pencil } from 'lucide-react';

export default function QCPage() {
    const [materials, setMaterials] = useState<any[]>([]);
    const [selectedMatId, setSelectedMatId] = useState<string>('');
    const [selectedAnalyte, setSelectedAnalyte] = useState<any>(null); // For Detail View
    const [runs, setRuns] = useState<any[]>([]); // Runs for selected Analyte

    // Modals
    const [showAddRun, setShowAddRun] = useState(false);
    const [runValue, setRunValue] = useState('');
    const [showEditDef, setShowEditDef] = useState(false); // Edit Thresholds
    const [editDefData, setEditDefData] = useState({ id: '', mean: '', sd: '' });
    const [showSeedConfirm, setShowSeedConfirm] = useState(false);

    // Create Modals
    const [showAddMaterial, setShowAddMaterial] = useState(false);
    const [newMaterial, setNewMaterial] = useState({ name: '', lot: '', department: 'Chemistry' });
    const [showAddAnalyte, setShowAddAnalyte] = useState(false);
    const [newAnalyte, setNewAnalyte] = useState({ testCode: '', testName: '', mean: '', sd: '', unit: '' });

    const [showEditMaterial, setShowEditMaterial] = useState(false);
    const [editMaterialData, setEditMaterialData] = useState({ id: '', name: '', lot: '', department: '' });

    const loadMaterials = async () => {
        const res = await fetch('/api/qc?type=materials');
        const data = await res.json();
        setMaterials(data);
        if (data.length > 0 && !selectedMatId) setSelectedMatId(data[0].id);
    };

    const loadRuns = async (defId: string) => {
        const res = await fetch(`/api/qc?type=runs&defId=${defId}`);
        const data = await res.json();
        setRuns(data);
    };

    useEffect(() => { loadMaterials(); }, []);

    const handleSeed = async () => {
        await fetch('/api/qc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'seed' })
        });
        loadMaterials();
        setShowSeedConfirm(false);
    };

    const handleAddRun = async () => {
        if (!runValue || !selectedAnalyte) return;
        await fetch('/api/qc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'run',
                data: { qcDefId: selectedAnalyte.id, value: parseFloat(runValue), userId: 'admin' }
            })
        });
        setRunValue('');
        setShowAddRun(false);
        loadRuns(selectedAnalyte.id);
    };

    const handleUpdateDef = async () => {
        await fetch('/api/qc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'update_definition',
                data: { id: editDefData.id, mean: editDefData.mean, sd: editDefData.sd }
            })
        });
        setShowEditDef(false);
        loadMaterials(); // Refresh to see new targets
        // If viewing specific analyte, refresh that context?
        if (selectedAnalyte && selectedAnalyte.id === editDefData.id) {
            setSelectedAnalyte({
                ...selectedAnalyte,
                mean: parseFloat(editDefData.mean),
                sd: parseFloat(editDefData.sd)
            });
        }
    };

    const openEditModal = (analyte: any) => {
        setEditDefData({
            id: analyte.id,
            mean: analyte.mean.toString(),
            sd: analyte.sd.toString()
        });
        setShowEditDef(true);
    };

    const viewAnalyte = (analyte: any) => {
        setSelectedAnalyte(analyte);
        setRuns([]); // Clear old runs
        loadRuns(analyte.id);
    };

    const selectedMaterial = materials.find(m => m.id === selectedMatId);

    // Chart Prep
    const chartData = runs.map(r => ({
        name: new Date(r.timestamp).toLocaleDateString(),
        value: r.value,
        timestamp: r.timestamp
    })).reverse(); // Runs loaded desc, need asc for chart

    const handleCreateMaterial = async () => {
        if (!newMaterial.name || !newMaterial.lot) return;
        await fetch('/api/qc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'create_material', data: newMaterial })
        });
        setNewMaterial({ name: '', lot: '', department: 'Chemistry' });
        setShowAddMaterial(false);
        loadMaterials();
    };

    const handleCreateAnalyte = async () => {
        if (!newAnalyte.testCode || !newAnalyte.mean || !selectedMaterial) return;
        await fetch('/api/qc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'create_definition',
                data: { ...newAnalyte, materialId: selectedMaterial.id, mean: parseFloat(newAnalyte.mean), sd: parseFloat(newAnalyte.sd) }
            })
        });
        setNewAnalyte({ testCode: '', testName: '', mean: '', sd: '', unit: '' });
        setShowAddAnalyte(false);
        loadMaterials();
    };

    const handleDeleteMaterial = async (id: string) => {
        if (!confirm('Are you sure? This will delete the material and all its analytes.')) return;
        await fetch('/api/qc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'delete_material', data: { id } })
        });
        if (selectedMatId === id) setSelectedMatId('');
        loadMaterials();
    };

    const handleDeleteAnalyte = async (id: string) => {
        if (!confirm('Delete this analyte definition?')) return;
        await fetch('/api/qc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'delete_definition', data: { id } })
        });
        loadMaterials();
    };

    const handleUpdateMaterial = async () => {
        await fetch('/api/qc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'update_material', data: editMaterialData })
        });
        setShowEditMaterial(false);
        loadMaterials();
    };

    const openEditMaterial = () => {
        if (!selectedMaterial) return;
        setEditMaterialData({
            id: selectedMaterial.id,
            name: selectedMaterial.name,
            lot: selectedMaterial.lot,
            department: selectedMaterial.department
        });
        setShowEditMaterial(true);
    };

    return (
        <div className="h-[calc(100vh-100px)] flex flex-col">
            {/* Header */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                        <Activity className="h-6 w-6 text-primary-600" />
                        QC Dashboard
                    </h1>
                    <p className="text-slate-500">Monitor instrument performance and control values</p>
                </div>
                <div className="flex gap-2">
                    <Button onClick={() => setShowAddMaterial(true)} variant="outline">
                        <Plus className="w-4 h-4 mr-2" /> New Material
                    </Button>
                    {materials.length === 0 && (
                        <Button onClick={() => setShowSeedConfirm(true)} variant="destructive">
                            <TestTube className="w-4 h-4 mr-2" />
                            Initialize Standard Controls
                        </Button>
                    )}
                </div>
            </div>

            <div className="flex flex-1 gap-6 overflow-hidden">
                {/* Sidebar: Materials */}
                <Card className="w-64 flex flex-col overflow-hidden">
                    <div className="p-4 bg-slate-50 border-b font-bold text-slate-700">Control Materials</div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                        {materials.map(mat => (
                            <div
                                key={mat.id}
                                onClick={() => { setSelectedMatId(mat.id); setSelectedAnalyte(null); }}
                                className={`p-3 rounded-md cursor-pointer text-sm transition-colors flex justify-between items-start group ${selectedMatId === mat.id ? 'bg-primary-50 text-primary-700 font-bold border border-primary-200' : 'hover:bg-slate-100 text-slate-600'}`}
                            >
                                <div>
                                    <div>{mat.name}</div>
                                    <div className="text-xs font-normal opacity-75">{mat.department} • {mat.lot}</div>
                                </div>
                                <Button variant="outline" className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500" onClick={(e) => { e.stopPropagation(); handleDeleteMaterial(mat.id); }}>
                                    <Trash2 className="h-4 w-4" />
                                </Button>
                            </div>
                        ))}
                    </div>
                </Card>

                {/* Main Content */}
                <div className="flex-1 flex flex-col gap-6 overflow-hidden">
                    {selectedMaterial && !selectedAnalyte && (
                        <div className="flex-1 overflow-y-auto">
                            <div className="flex justify-between items-center mb-4">
                                <div className="flex items-center gap-2">
                                    <h2 className="text-xl font-bold">{selectedMaterial.name} <span className="text-base font-normal text-slate-500">({selectedMaterial.analytes.length} Analytes)</span></h2>
                                    <Button variant="outline" onClick={openEditMaterial}>
                                        <Pencil className="h-4 w-4 text-slate-400" />
                                    </Button>
                                </div>
                                <Button onClick={() => setShowAddAnalyte(true)}>
                                    <Plus className="w-4 h-4 mr-2" /> Add Analyte
                                </Button>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {selectedMaterial.analytes.map((analyte: any) => (
                                    <Card key={analyte.id} className="p-4 hover:shadow-md transition-shadow relative group">
                                        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                                            <Button variant="outline" onClick={(e) => { e.stopPropagation(); openEditModal(analyte); }}>
                                                <Settings className="h-4 w-4 text-slate-400 hover:text-primary-600" />
                                            </Button>
                                            <Button variant="outline" onClick={(e) => { e.stopPropagation(); handleDeleteAnalyte(analyte.id); }}>
                                                <Trash2 className="h-4 w-4 text-slate-400 hover:text-red-500" />
                                            </Button>
                                        </div>
                                        <div onClick={() => viewAnalyte(analyte)} className="cursor-pointer space-y-3">
                                            <div>
                                                <div className="font-bold text-lg text-slate-800">{analyte.testName} ({analyte.testCode})</div>
                                                <div className="text-xs text-slate-500">Target: {analyte.mean} {analyte.unit} ± {analyte.sd}</div>
                                            </div>
                                            <div className="h-1 bg-slate-100 rounded overflow-hidden">
                                                <div className="h-full bg-green-500 w-full opacity-50"></div>
                                            </div>
                                            <div className="flex justify-between items-center text-xs text-primary-600 font-bold">
                                                <span>Click to View Chart</span>
                                                <Activity className="h-3 w-3" />
                                            </div>
                                        </div>
                                    </Card>
                                ))}
                            </div>
                        </div>
                    )}

                    {selectedAnalyte && (
                        <Card className="flex-1 flex flex-col overflow-hidden">
                            <div className="p-4 border-b flex justify-between items-center bg-slate-50">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <Button variant="outline" onClick={() => setSelectedAnalyte(null)}>← Back</Button>
                                        <h2 className="text-lg font-bold">{selectedAnalyte.testName} ({selectedMaterial?.name})</h2>
                                    </div>
                                    <div className="ml-16 text-sm text-slate-500">Mean: {selectedAnalyte.mean} | SD: {selectedAnalyte.sd} | Unit: {selectedAnalyte.unit}</div>
                                </div>
                                <div className="flex gap-2">
                                    <Button variant="outline" onClick={() => openEditModal(selectedAnalyte)}>
                                        <Settings className="w-4 h-4 mr-2" /> Edit Targets
                                    </Button>
                                    <Button onClick={() => setShowAddRun(true)}>
                                        <Plus className="w-4 h-4 mr-2" /> Add Run
                                    </Button>
                                </div>
                            </div>
                            <div className="flex-1 p-4">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                                        <YAxis domain={['auto', 'auto']} stroke="#64748b" fontSize={12} />
                                        <Tooltip />
                                        <ReferenceLine y={selectedAnalyte.mean} stroke="#0f172a" label="Mean" />
                                        <ReferenceLine y={selectedAnalyte.mean + 2 * selectedAnalyte.sd} stroke="#f59e0b" label="+2SD" />
                                        <ReferenceLine y={selectedAnalyte.mean - 2 * selectedAnalyte.sd} stroke="#f59e0b" label="-2SD" />
                                        <ReferenceLine y={selectedAnalyte.mean + 3 * selectedAnalyte.sd} stroke="#ef4444" label="+3SD" />
                                        <ReferenceLine y={selectedAnalyte.mean - 3 * selectedAnalyte.sd} stroke="#ef4444" label="-3SD" />
                                        <Line type="monotone" dataKey="value" stroke="#0ea5e9" strokeWidth={2} dot={{ r: 4 }} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </Card>
                    )}
                </div>
            </div>

            {/* Edit Definition Modal */}
            {showEditDef && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-96 p-6 bg-white shadow-xl space-y-4">
                        <h3 className="text-lg font-bold">Edit Target Values</h3>
                        <p className="text-sm text-slate-500">Adjusting these values creates a new QC period logic (technically).</p>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">New Mean</label>
                                <Input value={editDefData.mean} onChange={e => setEditDefData({ ...editDefData, mean: e.target.value })} type="number" />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">New SD</label>
                                <Input value={editDefData.sd} onChange={e => setEditDefData({ ...editDefData, sd: e.target.value })} type="number" />
                            </div>
                        </div>
                        <div className="flex justify-end gap-2">
                            <Button variant="outline" onClick={() => setShowEditDef(false)}>Cancel</Button>
                            <Button onClick={handleUpdateDef}>Save Changes</Button>
                        </div>
                    </Card>
                </div>
            )}

            {/* Add Run Modal */}
            {showAddRun && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-80 p-6 bg-white shadow-xl space-y-4">
                        <h3 className="text-lg font-bold">Add QC Result</h3>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Value ({selectedAnalyte?.unit})</label>
                            <Input value={runValue} onChange={e => setRunValue(e.target.value)} type="number" autoFocus />
                        </div>
                        <div className="flex justify-end gap-2">
                            <Button variant="outline" onClick={() => setShowAddRun(false)}>Cancel</Button>
                            <Button onClick={handleAddRun}>Add Run</Button>
                        </div>
                    </Card>
                </div>
            )}

            {/* Add Material Modal */}
            {showAddMaterial && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-96 p-6 bg-white shadow-xl space-y-4">
                        <h3 className="text-lg font-bold">New Control Material</h3>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Material Name (e.g. Heme Low)</label>
                            <Input value={newMaterial.name} onChange={e => setNewMaterial({ ...newMaterial, name: e.target.value })} autoFocus />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Lot Number</label>
                            <Input value={newMaterial.lot} onChange={e => setNewMaterial({ ...newMaterial, lot: e.target.value })} />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Department</label>
                            <Input value={newMaterial.department} onChange={e => setNewMaterial({ ...newMaterial, department: e.target.value })} placeholder="Chemistry" />
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                            <Button variant="outline" onClick={() => setShowAddMaterial(false)}>Cancel</Button>
                            <Button onClick={handleCreateMaterial}>Create Material</Button>
                        </div>
                    </Card>
                </div>
            )}

            {/* Add Analyte Modal */}
            {showAddAnalyte && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-96 p-6 bg-white shadow-xl space-y-4">
                        <h3 className="text-lg font-bold">Add Analyte Definition</h3>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Test Name (e.g. Glucose)</label>
                            <Input value={newAnalyte.testName} onChange={e => setNewAnalyte({ ...newAnalyte, testName: e.target.value })} autoFocus />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Test Code (GLU)</label>
                                <Input value={newAnalyte.testCode} onChange={e => setNewAnalyte({ ...newAnalyte, testCode: e.target.value })} />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Units (mg/dL)</label>
                                <Input value={newAnalyte.unit} onChange={e => setNewAnalyte({ ...newAnalyte, unit: e.target.value })} />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Mean</label>
                                <Input value={newAnalyte.mean} onChange={e => setNewAnalyte({ ...newAnalyte, mean: e.target.value })} type="number" />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">SD</label>
                                <Input value={newAnalyte.sd} onChange={e => setNewAnalyte({ ...newAnalyte, sd: e.target.value })} type="number" />
                            </div>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                            <Button variant="outline" onClick={() => setShowAddAnalyte(false)}>Cancel</Button>
                            <Button onClick={handleCreateAnalyte}>Add Definition</Button>
                        </div>
                    </Card>
                </div>
            )}

            {/* Edit Material Modal */}
            {showEditMaterial && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-96 p-6 bg-white shadow-xl space-y-4">
                        <h3 className="text-lg font-bold">Edit Control Material</h3>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Material Name</label>
                            <Input value={editMaterialData.name} onChange={e => setEditMaterialData({ ...editMaterialData, name: e.target.value })} />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Lot Number</label>
                            <Input value={editMaterialData.lot} onChange={e => setEditMaterialData({ ...editMaterialData, lot: e.target.value })} />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Department</label>
                            <Input value={editMaterialData.department} onChange={e => setEditMaterialData({ ...editMaterialData, department: e.target.value })} />
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                            <Button variant="outline" onClick={() => setShowEditMaterial(false)}>Cancel</Button>
                            <Button onClick={handleUpdateMaterial}>Save Changes</Button>
                        </div>
                    </Card>
                </div>
            )}

            {/* Seed Confirm Modal */}
            {showSeedConfirm && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-96 p-6 bg-white shadow-xl space-y-4">
                        <div className="flex items-center gap-2 text-red-600">
                            <AlertCircle className="h-6 w-6" />
                            <h3 className="text-lg font-bold">Initialize Database?</h3>
                        </div>
                        <p className="text-sm text-slate-600">
                            This will <strong>erase all existing QC data</strong> and populate the system with standard Hematology and Chemistry controls. This action cannot be undone.
                        </p>
                        <div className="flex justify-end gap-2 pt-2">
                            <Button variant="outline" onClick={() => setShowSeedConfirm(false)}>Cancel</Button>
                            <Button variant="destructive" onClick={handleSeed}>Yes, Initialize</Button>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
}
