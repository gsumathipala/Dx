"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/button';
import { Mail, Send, Trash2, AlertCircle, User, CheckCircle } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

export default function MessagesPage() {
    const { user } = useAuth();
    const [messages, setMessages] = useState<any[]>([]);
    const [users, setUsers] = useState<any[]>([]);
    const [departments, setDepartments] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCompose, setShowCompose] = useState(false);

    // Compose State
    const [sendMode, setSendMode] = useState<'user' | 'department'>('user');
    const [toUser, setToUser] = useState('');
    const [toDepartment, setToDepartment] = useState('');
    const [content, setContent] = useState('');
    const [urgent, setUrgent] = useState(false);

    const loadDeps = async () => {
        const res = await fetch('/api/admin/departments');
        if (res.ok) setDepartments(await res.json());
    };

    const loadMessages = async () => {
        const res = await fetch('/api/messages');
        if (res.ok) setMessages(await res.json());
        setLoading(false);
    };

    const loadUsers = async () => {
        const res = await fetch('/api/users/list');
        if (res.ok) setUsers(await res.json());
    };

    useEffect(() => {
        loadMessages();
        loadUsers();
        loadDeps();
    }, []);

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault();

        const payload: any = { content, urgent };
        if (sendMode === 'user') {
            if (!toUser) return;
            payload.toUser = toUser;
        } else {
            if (!toDepartment) return;
            payload.toDepartment = toDepartment;
        }

        await fetch('/api/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        setShowCompose(false);
        setContent('');
        setUrgent(false);
        alert('Message sent!');
    };

    const markRead = async (msg: any) => {
        if (msg.read) return;
        await fetch('/api/messages', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: msg.id, action: 'mark_read' })
        });
        loadMessages(); // Refresh to update UI
    };

    const deleteMessage = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm('Delete message?')) return;
        await fetch('/api/messages', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, action: 'delete' })
        });
        loadMessages();
    };

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Internal Messages</h1>
                    <p className="text-slate-500">Secure communication with lab staff.</p>
                </div>
                <Button onClick={() => setShowCompose(true)} className="bg-primary-600">
                    <Send className="w-4 h-4 mr-2" /> New Message
                </Button>
            </div>

            <div className="grid gap-4">
                {messages.length === 0 && !loading && (
                    <div className="text-center p-12 bg-slate-50 rounded border border-dashed border-slate-300">
                        <Mail className="w-12 h-12 mx-auto text-slate-300 mb-2" />
                        <p className="text-slate-500">Your inbox is empty.</p>
                    </div>
                )}

                {messages.map((msg) => (
                    <div
                        key={msg.id}
                        onClick={() => markRead(msg)}
                        className={`p-4 rounded-lg border cursor-pointer transition-all ${msg.read ? 'bg-white border-slate-200' : 'bg-blue-50 border-blue-200 shadow-sm'}`}
                    >
                        <div className="flex justify-between items-start mb-2">
                            <div className="flex items-center gap-2">
                                <div className={`p-2 rounded-full ${msg.urgent ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-600'}`}>
                                    <User className="w-4 h-4" />
                                </div>
                                <div>
                                    <div className="font-bold text-slate-900">
                                        {msg.fromName} <span className="text-slate-400 font-normal text-xs">(@{msg.fromUser})</span>
                                    </div>
                                    <div className="text-xs text-slate-500">{new Date(msg.createdAt).toLocaleString()}</div>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                {msg.urgent && <span className="bg-red-100 text-red-700 text-xs px-2 py-1 rounded font-bold flex items-center gap-1"><AlertCircle className="w-3 h-3" /> URGENT</span>}
                                {!msg.read && <span className="bg-blue-600 text-white text-[10px] px-2 py-1 rounded-full">NEW</span>}
                                <button onClick={(e) => deleteMessage(msg.id, e)} className="p-2 hover:bg-slate-100 rounded text-slate-400 hover:text-red-500">
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                        <p className={`text-slate-700 whitespace-pre-wrap ${!msg.read && 'font-medium'}`}>{msg.content}</p>
                    </div>
                ))}
            </div>

            {/* COMPOSE MODAL */}
            {showCompose && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                    <Card className="w-full max-w-lg bg-white shadow-2xl animate-in fade-in zoom-in duration-200">
                        <form onSubmit={handleSend} className="space-y-4">
                            <div className="flex justify-between items-center border-b pb-4">
                                <h2 className="text-xl font-bold flex items-center gap-2"><Send className="w-5 h-5 text-primary-600" /> Send Message</h2>
                                <button type="button" onClick={() => setShowCompose(false)} className="text-slate-400 hover:text-slate-600">✕</button>
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-2">Recipient</label>

                                <div className="flex gap-2 mb-3 bg-slate-100 p-1 rounded-lg w-fit">
                                    <button
                                        type="button"
                                        onClick={() => setSendMode('user')}
                                        className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${sendMode === 'user' ? 'bg-white shadow text-primary-600' : 'text-slate-500'}`}
                                    >
                                        Specific User
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setSendMode('department')}
                                        className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${sendMode === 'department' ? 'bg-white shadow text-primary-600' : 'text-slate-500'}`}
                                    >
                                        Entire Department
                                    </button>
                                </div>

                                {sendMode === 'user' ? (
                                    <select
                                        className="w-full p-2 border rounded bg-slate-50"
                                        value={toUser}
                                        onChange={(e) => setToUser(e.target.value)}
                                        required
                                    >
                                        <option value="">Select User...</option>
                                        {users.filter(u => u.username !== user?.username).map(u => (
                                            <option key={u.username} value={u.username}>{u.name} ({u.role})</option>
                                        ))}
                                    </select>
                                ) : (
                                    <select
                                        className="w-full p-2 border rounded bg-slate-50"
                                        value={toDepartment}
                                        onChange={(e) => setToDepartment(e.target.value)}
                                        required
                                    >
                                        <option value="">Select Department to Broadcast...</option>
                                        <option value="General">General / All Staff</option>
                                        {departments.map(d => (
                                            <option key={d.id} value={d.name}>{d.name} ({d.code})</option>
                                        ))}
                                    </select>
                                )}
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1">Message</label>
                                <textarea
                                    className="w-full p-2 border rounded min-h-[120px]"
                                    placeholder="Type your message here..."
                                    value={content}
                                    onChange={(e) => setContent(e.target.value)}
                                    required
                                />
                            </div>

                            <label className="flex items-center gap-2 cursor-pointer">
                                <input type="checkbox" checked={urgent} onChange={e => setUrgent(e.target.checked)} className="w-4 h-4 text-red-600 rounded" />
                                <span className="text-sm font-medium text-slate-700">Mark as Urgent</span>
                            </label>

                            <div className="flex justify-end gap-3 pt-2">
                                <Button type="button" variant="outline" onClick={() => setShowCompose(false)}>Cancel</Button>
                                <Button type="submit" className="bg-primary-600 hover:bg-primary-700">Send Message</Button>
                            </div>
                        </form>
                    </Card>
                </div>
            )}
        </div>
    );
}
