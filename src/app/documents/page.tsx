"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { useAuth } from '@/context/AuthContext';
import { FileText, Upload as UploadIcon, Filter, History, Trash2, StopCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table } from '@/components/ui/Table';

export default function DocumentsPage() {
    const { user } = useAuth();
    const [documents, setDocuments] = useState<any[]>([]);
    const [filterCategory, setFilterCategory] = useState('All');
    const [showObsolete, setShowObsolete] = useState(false);
    const [showUpload, setShowUpload] = useState(false);
    const [uploadMode, setUploadMode] = useState<'NEW' | 'REVISE'>('NEW');
    const [parentDoc, setParentDoc] = useState<any>(null); // For revisions

    // Form State
    const [formData, setFormData] = useState({
        title: '',
        category: 'SOP',
        version: '1.0',
        effectiveDate: new Date().toISOString().split('T')[0],
        file: null as File | null
    });

    const isAdmin = user && ['admin', 'manager'].includes(user.role);

    const loadDocs = async () => {
        const res = await fetch('/api/documents');
        if (res.ok) setDocuments(await res.json());
    };

    useEffect(() => { loadDocs(); }, []);

    const handleUpload = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!formData.file) return alert('File required');

        const body = new FormData();
        body.append('file', formData.file);
        body.append('title', formData.title);
        body.append('category', formData.category);
        body.append('version', formData.version);
        body.append('effectiveDate', formData.effectiveDate);
        body.append('action', uploadMode);

        if (uploadMode === 'REVISE' && parentDoc) {
            body.append('parentId', parentDoc.id);
        }

        try {
            const res = await fetch('/api/documents', { method: 'POST', body });
            if (res.ok) {
                setShowUpload(false);
                loadDocs();
                resetForm();
            } else {
                alert('Upload failed');
            }
        } catch (e) { console.error(e); }
    };

    const resetForm = () => {
        setFormData({ title: '', category: 'SOP', version: '1.0', effectiveDate: new Date().toISOString().split('T')[0], file: null });
        setParentDoc(null);
        setUploadMode('NEW');
    };

    const initiateRevision = (doc: any) => {
        setUploadMode('REVISE');
        setParentDoc(doc);
        setFormData({
            ...formData,
            title: doc.title,
            category: doc.category,
            version: (parseFloat(doc.version) + 1).toFixed(1), // Auto-increment hint
            effectiveDate: new Date().toISOString().split('T')[0]
        });
        setShowUpload(true);
    };

    const toggleStatus = async (id: string, currentStatus: string) => {
        const newStatus = currentStatus === 'Active' ? 'Obsolete' : 'Active';
        if (!confirm(`Mark document as ${newStatus}?`)) return;

        await fetch('/api/documents', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, status: newStatus })
        });
        loadDocs();
    };

    // Filter Logic
    const filteredDocs = documents
        .filter(d => (showObsolete ? true : d.status === 'Active'))
        .filter(d => (filterCategory === 'All' ? true : d.category === filterCategory))
        .sort((a, b) => new Date(b.uploadsAt).getTime() - new Date(a.uploadsAt).getTime()); // Newest first

    const columns = [
        {
            header: 'Status', accessor: (d: any) => (
                <span className={`px-2 py-1 rounded text-xs font-bold ${d.status === 'Active' ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-500'}`}>
                    {d.status}
                </span>
            )
        },
        {
            header: 'Document', accessor: (d: any) => (
                <div>
                    <a href={d.filePath} target="_blank" className="font-bold text-primary-700 hover:underline flex items-center gap-2">
                        <FileText className="w-4 h-4" /> {d.title}
                    </a>
                    <div className="text-xs text-slate-400">{d.category}</div>
                </div>
            )
        },
        { header: 'Rev', accessor: (d: any) => <span className="font-mono">{d.version}</span> },
        { header: 'Effective', accessor: (d: any) => d.effectiveDate },
        {
            header: 'Actions', accessor: (d: any) => isAdmin && (
                <div className="flex gap-2">
                    {d.status === 'Active' && (
                        <Button variant="outline" className="h-8 w-8 p-0" onClick={() => initiateRevision(d)} title="Issue Revision">
                            <RefreshCw className="w-3 h-3" />
                        </Button>
                    )}
                    <Button variant="outline" className="h-8 w-8 p-0 border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700 hover:border-red-300" onClick={() => toggleStatus(d.id, d.status)} title="Archive/Obsolete">
                        <StopCircle className="w-3 h-3" />
                    </Button>
                </div>
            )
        }
    ];

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Document Control</h1>
                    <p className="text-slate-500">Authorized Standard Operating Procedures and Manuals.</p>
                </div>
                {isAdmin && (
                    <Button onClick={() => { resetForm(); setShowUpload(true); }} className="bg-primary-600">
                        <UploadIcon className="w-4 h-4 mr-2" /> Upload Document
                    </Button>
                )}
            </div>

            {/* FILTERS */}
            <div className="flex gap-4 items-center bg-slate-50 p-4 rounded border border-slate-200">
                <Filter className="w-4 h-4 text-slate-500" />
                <select
                    className="bg-white border rounded px-2 py-1 text-sm font-medium"
                    value={filterCategory}
                    onChange={e => setFilterCategory(e.target.value)}
                >
                    <option value="All">All Categories</option>
                    <option value="SOP">SOP</option>
                    <option value="Policy">Policy</option>
                    <option value="Form">Form</option>
                    <option value="Manual">Manual</option>
                </select>

                <label className="flex items-center gap-2 text-sm text-slate-600 ml-auto cursor-pointer">
                    <input type="checkbox" checked={showObsolete} onChange={e => setShowObsolete(e.target.checked)} />
                    Show Obsolete/Archived
                </label>
            </div>

            {/* LIST */}
            <Card className="overflow-hidden">
                <Table data={filteredDocs} columns={columns} keyField="id" emptyMessage="No active documents found." />
            </Card>

            {/* UPLOAD MODAL */}
            {showUpload && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-in fade-in">
                    <Card className="w-full max-w-lg bg-white shadow-xl">
                        <div className="flex justify-between items-center mb-4 border-b pb-4">
                            <h2 className="text-xl font-bold">{uploadMode === 'REVISE' ? `Revise: ${parentDoc?.title}` : 'Upload New Document'}</h2>
                            <button onClick={() => setShowUpload(false)}><span className="sr-only">Close</span>✕</button>
                        </div>
                        <form onSubmit={handleUpload} className="space-y-4">
                            <div className="space-y-2">
                                <Label>Document Title</Label>
                                <Input value={formData.title} onChange={e => setFormData({ ...formData, title: e.target.value })} required />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Category</Label>
                                    <select
                                        className="w-full border rounded p-2"
                                        value={formData.category}
                                        onChange={e => setFormData({ ...formData, category: e.target.value })}
                                    >
                                        <option value="SOP">SOP</option>
                                        <option value="Policy">Policy</option>
                                        <option value="Form">Form</option>
                                        <option value="Manual">Manual</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <Label>Version (Rev)</Label>
                                    <Input value={formData.version} onChange={e => setFormData({ ...formData, version: e.target.value })} required />
                                </div>
                            </div>
                            <div className="space-y-2">
                                <Label>Effective Date</Label>
                                <Input type="date" value={formData.effectiveDate} onChange={e => setFormData({ ...formData, effectiveDate: e.target.value })} required />
                            </div>
                            <div className="space-y-2">
                                <Label>File (PDF)</Label>
                                <Input type="file" accept=".pdf,.doc,.docx" onChange={e => setFormData({ ...formData, file: e.target.files?.[0] || null })} required />
                            </div>
                            <Button type="submit" className="w-full mt-4">
                                {uploadMode === 'REVISE' ? 'Publish Revision' : 'Upload Document'}
                            </Button>
                        </form>
                    </Card>
                </div>
            )}
        </div>
    );
}
