"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StatusBadge } from '@/components/ui/Badge';

export default function HistologyPage() {
    const [orders, setOrders] = useState<any[]>([]);
    const [selectedOrder, setSelectedOrder] = useState<any>(null);
    const [assets, setAssets] = useState<{ blocks: any[], slides: any[] }>({ blocks: [], slides: [] });

    // Forms
    const [grossingCount, setGrossingCount] = useState(1);
    const [grossingNotes, setGrossingNotes] = useState('');
    const [selectedBlock, setSelectedBlock] = useState<any>(null);
    const [microtomyCount, setMicrotomyCount] = useState(1);

    const loadOrders = () => {
        fetch('/api/orders').then(r => r.json()).then(data => {
            // Filter for orders that might be Histo (simulated by checking if ID implies it or just all)
            // For demo, show all 'In Progress' orders
            setOrders(data.filter((o: any) => o.status !== 'Completed'));
        });
    };

    const loadAssets = async (accNum: string) => {
        const res = await fetch(`/api/histology?accessionNumber=${accNum}`);
        setAssets(await res.json());
    };

    useEffect(() => { loadOrders(); }, []);
    useEffect(() => {
        if (selectedOrder) loadAssets(selectedOrder.accessionNumber);
    }, [selectedOrder]);

    const handleGrossing = async (e: React.FormEvent) => {
        e.preventDefault();
        await fetch('/api/histology', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'grossing',
                accessionNumber: selectedOrder.accessionNumber,
                count: Number(grossingCount),
                notes: grossingNotes
            })
        });
        loadAssets(selectedOrder.accessionNumber);
        setGrossingNotes('');
    };

    const handleMicrotomy = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedBlock) return alert("Select a block first");
        await fetch('/api/histology', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'microtomy',
                accessionNumber: selectedOrder.accessionNumber,
                blockId: selectedBlock.id,
                count: Number(microtomyCount)
            })
        });
        loadAssets(selectedOrder.accessionNumber);
    };

    return (
        <div className="flex gap-6 min-h-[500px]">
            {/* Worklist */}
            <div className="w-1/4 flex flex-col gap-4">
                <Card className="flex-1 p-0 overflow-hidden" title="Specimen Reception">
                    <div className="overflow-y-auto p-2 space-y-2">
                        {orders.map(o => (
                            <div key={o.id} onClick={() => { setSelectedOrder(o); setSelectedBlock(null); }} className={`p-3 rounded border cursor-pointer border-l-4 ${selectedOrder?.id === o.id ? 'bg-primary-50 border-l-primary-500' : 'bg-white border-l-slate-300'}`}>
                                <div className="font-bold font-mono">{o.accessionNumber}</div>
                                <div className="text-xs text-slate-500 truncate">{o.testIds?.join(', ')}</div>
                            </div>
                        ))}
                    </div>
                </Card>
            </div>

            {/* Workflow Area */}
            <div className="flex-1 flex flex-col gap-6 overflow-y-auto">
                {selectedOrder ? (
                    <>
                        <div className="grid grid-cols-2 gap-6">
                            {/* Grossing Station */}
                            <Card title="🔪 Grossing Station (Block Creation)">
                                <form onSubmit={handleGrossing} className="space-y-4">
                                    <div className="flex justify-between items-center text-sm font-bold bg-slate-100 p-2 rounded">
                                        <span>Specimen: {selectedOrder.accessionNumber}</span>
                                    </div>
                                    <div className="flex gap-4">
                                        <div className="flex-1">
                                            <label className="label"># of Cassettes (Blocks)</label>
                                            <input type="number" min="1" max="10" className="input-field" value={grossingCount} onChange={e => setGrossingCount(Number(e.target.value))} />
                                        </div>
                                        <button type="submit" className="btn-primary self-end">Print Cassettes 🖨️</button>
                                    </div>
                                    <input className="input-field text-sm" placeholder="Grossing Notes (e.g. 'Tumor 2cm')..." value={grossingNotes} onChange={e => setGrossingNotes(e.target.value)} />
                                </form>
                            </Card>

                            {/* Microtomy Station */}
                            <Card title="🔬 Microtomy Station (Slide Cutting)">
                                <form onSubmit={handleMicrotomy} className="space-y-4">
                                    <div className="flex justify-between items-center text-sm font-bold bg-purple-100 text-purple-900 p-2 rounded">
                                        <span>Target Block: {selectedBlock ? selectedBlock.id : 'None Selected'}</span>
                                    </div>
                                    <div className="flex gap-4">
                                        <div className="flex-1">
                                            <label className="label"># of Slides</label>
                                            <input type="number" min="1" max="10" className="input-field" value={microtomyCount} onChange={e => setMicrotomyCount(Number(e.target.value))} />
                                        </div>
                                        <button type="submit" disabled={!selectedBlock} className="btn-primary self-end disabled:opacity-50">Print Labels 🏷️</button>
                                    </div>
                                </form>
                            </Card>
                        </div>

                        {/* Hierarchical View */}
                        <Card title="Asset Hierarchy (Tracking)">
                            <div className="space-y-4">
                                {assets.blocks.length === 0 && <p className="text-slate-400 italic">No assets created yet.</p>}

                                {assets.blocks.map(block => (
                                    <div key={block.id} className="border rounded-lg p-4 bg-slate-50">
                                        <div className="flex justify-between items-center mb-2">
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => setSelectedBlock(block)}
                                                    className={`px-2 py-1 rounded text-sm font-bold flex items-center gap-2 ${selectedBlock?.id === block.id ? 'bg-purple-600 text-white ring-2 ring-offset-2 ring-purple-600' : 'bg-white border hover:bg-slate-100'}`}
                                                >
                                                    📦 {block.id}
                                                </button>
                                                <span className="text-xs text-slate-500 italic">{block.notes}</span>
                                            </div>
                                            <Badge variant="warning">{block.status}</Badge>
                                        </div>

                                        {/* Slides for this block */}
                                        <div className="ml-8 flex flex-wrap gap-2">
                                            {assets.slides.filter(s => s.blockId === block.id).map(slide => (
                                                <div key={slide.id} className="bg-white border border-blue-200 text-blue-800 px-3 py-1 rounded text-xs font-mono shadow-sm flex items-center gap-1">
                                                    🔹 {slide.id}
                                                </div>
                                            ))}
                                            {assets.slides.filter(s => s.blockId === block.id).length === 0 && <span className="text-xs text-slate-400">No slides cut</span>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </Card>
                    </>
                ) : (
                    <div className="flex items-center justify-center h-full text-slate-400">Select specimen to process</div>
                )}
            </div>
        </div>
    );
}
