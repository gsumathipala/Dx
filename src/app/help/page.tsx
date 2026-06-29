"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { RichTextEditor } from '@/components/ui/RichTextEditor';
import { useAuth } from '@/context/AuthContext';
import { Edit2, Save, Plus, Trash2, X, MoveUp, MoveDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function HelpPage() {
    const { user } = useAuth();
    const [sections, setSections] = useState<any[]>([]);
    const [openCategory, setOpenCategory] = useState<string | null>(null);
    const [isEditing, setIsEditing] = useState(false);
    const [unsavedChanges, setUnsavedChanges] = useState(false);

    const canEdit = user && ['admin', 'manager'].includes(user.role);

    const loadManual = async () => {
        try {
            const res = await fetch('/api/help');
            if (res.ok) {
                const data = await res.json();
                setSections(data);
                if (data.length > 0) setOpenCategory(data[0].category);
            }
        } catch (e) { console.error(e); }
    };

    useEffect(() => { loadManual(); }, []);

    const saveManual = async () => {
        try {
            const res = await fetch('/api/help', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(sections)
            });
            if (res.ok) {
                setUnsavedChanges(false);
                setIsEditing(false);
                alert('Manual updated successfully!');
            }
        } catch (e) { alert('Failed to save'); }
    };

    // --- State Setters for Editing ---
    const updateSection = (idx: number, field: string, value: any) => {
        const newSecs = [...sections];
        newSecs[idx] = { ...newSecs[idx], [field]: value };
        setSections(newSecs);
        setUnsavedChanges(true);
    };

    const deleteSection = (idx: number) => {
        if (!confirm('Delete this entire section?')) return;
        const newSecs = sections.filter((_, i) => i !== idx);
        setSections(newSecs);
        setUnsavedChanges(true);
    };

    const addItem = (secIdx: number) => {
        const newSecs = [...sections];
        newSecs[secIdx].items.push({ title: 'New Topic', content: '<p>Content goes here...</p>' });
        setSections(newSecs);
        setUnsavedChanges(true);
        setOpenCategory(newSecs[secIdx].category);
    };

    const updateItem = (secIdx: number, itemIdx: number, field: string, value: any) => {
        const newSecs = [...sections];
        newSecs[secIdx].items[itemIdx] = { ...newSecs[secIdx].items[itemIdx], [field]: value };
        setSections(newSecs);
        setUnsavedChanges(true);
    };

    const deleteItem = (secIdx: number, itemIdx: number) => {
        if (!confirm('Delete this topic?')) return;
        const newSecs = [...sections];
        newSecs[secIdx].items.splice(itemIdx, 1);
        setSections(newSecs);
        setUnsavedChanges(true);
    };

    const addSection = () => {
        setSections([...sections, {
            id: `sec-${Date.now()}`,
            category: "New Section",
            items: []
        }]);
        setUnsavedChanges(true);
    };

    return (
        <div className="max-w-4xl space-y-6 pb-20">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Reference Manual</h1>
                    <p className="text-slate-500">Standard operating procedures and training resources.</p>
                </div>
                {canEdit && (
                    <div className="flex gap-2">
                        {isEditing ? (
                            <>
                                <Button variant="outline" onClick={() => setIsEditing(false)}>Cancel</Button>
                                <Button onClick={saveManual} className="bg-green-600 hover:bg-green-700">
                                    <Save className="w-4 h-4 mr-2" /> Save Changes
                                </Button>
                            </>
                        ) : (
                            <Button variant="outline" onClick={() => setIsEditing(true)}>
                                <Edit2 className="w-4 h-4 mr-2" /> Edit Manual
                            </Button>
                        )}
                    </div>
                )}
            </div>

            {isEditing && (
                <Alert className="bg-blue-50 border-blue-200">
                    <AlertDescription>
                        You are in <strong>Edit Mode</strong>. You can rename sections, add topics, and edit content using HTML tags.
                        Rearrange feature coming soon. Don&apos;t forget to <strong>Save Changes</strong>.
                    </AlertDescription>
                </Alert>
            )}

            <div className="grid grid-cols-1 gap-6">
                {sections.map((section, secIdx) => (
                    <Card key={section.id || secIdx} className="p-0 overflow-hidden shadow-sm hover:shadow-md transition-shadow">
                        <div className={`w-full p-4 flex justify-between items-center transition-colors ${openCategory === section.category ? 'bg-slate-800 text-white' : 'bg-white text-slate-800'}`}>
                            {isEditing ? (
                                <div className="flex-1 flex gap-2 items-center">
                                    <Input
                                        value={section.category}
                                        onChange={e => updateSection(secIdx, 'category', e.target.value)}
                                        className="text-slate-900 bg-white h-8"
                                    />
                                    <Button variant="destructive" className="h-8 px-3" onClick={() => deleteSection(secIdx)}><Trash2 className="w-4 h-4" /></Button>
                                </div>
                            ) : (
                                <button
                                    className="flex-1 text-left font-bold text-lg flex justify-between items-center"
                                    onClick={() => setOpenCategory(openCategory === section.category ? null : section.category)}
                                >
                                    {section.category}
                                    <span className="text-xl font-normal">{openCategory === section.category ? '−' : '+'}</span>
                                </button>
                            )}
                        </div>

                        {(openCategory === section.category || isEditing) && (
                            <div className="p-6 bg-white space-y-8 animate-in fade-in duration-300">
                                {section.items.map((item: any, itemIdx: number) => (
                                    <div key={itemIdx} className="border-b last:border-0 pb-6 last:pb-0 border-slate-100">
                                        {isEditing ? (
                                            <div className="space-y-3 bg-slate-50 p-4 rounded border border-slate-200">
                                                <div className="flex justify-between items-center">
                                                    <Input
                                                        value={item.title}
                                                        onChange={e => updateItem(secIdx, itemIdx, 'title', e.target.value)}
                                                        className="font-bold bg-white"
                                                        placeholder="Topic Title"
                                                    />
                                                    <Button variant="outline" className="h-8 px-2 text-red-500" onClick={() => deleteItem(secIdx, itemIdx)}><X className="w-4 h-4" /></Button>
                                                </div>
                                                <RichTextEditor
                                                    value={item.content}
                                                    onChange={(val: string) => updateItem(secIdx, itemIdx, 'content', val)}
                                                    className="h-64"
                                                />
                                            </div>
                                        ) : (
                                            <>
                                                <h3 className="text-xl font-bold text-slate-900 mb-3 flex items-center gap-2">
                                                    <span className="w-1.5 h-6 bg-primary-500 rounded-full inline-block"></span>
                                                    {item.title}
                                                </h3>
                                                <div
                                                    className="text-slate-600 leading-relaxed text-base pl-4 prose max-w-none"
                                                    dangerouslySetInnerHTML={{ __html: item.content }}
                                                />
                                            </>
                                        )}
                                    </div>
                                ))}

                                {isEditing && (
                                    <Button variant="outline" onClick={() => addItem(secIdx)} className="h-8 px-3 w-full border-dashed border-2">
                                        <Plus className="w-4 h-4 mr-2" /> Add Topic to {section.category}
                                    </Button>
                                )}
                            </div>
                        )}
                    </Card>
                ))}

                {isEditing && (
                    <Button onClick={addSection} variant="outline" className="w-full py-8 border-dashed border-2 text-lg">
                        <Plus className="w-5 h-5 mr-2" /> Add New Section
                    </Button>
                )}
            </div>
        </div>
    );
}
