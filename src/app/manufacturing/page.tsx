"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Table } from '@/components/ui/Table';
import { formatDateTime, formatDate } from '@/lib/utils'; // fix import if needed

export default function ManufacturingPage() {
    const [recipes, setRecipes] = useState<any[]>([]);
    const [runs, setRuns] = useState<any[]>([]);
    const [activeTab, setActiveTab] = useState<'runs' | 'recipes'>('runs');

    // Forms
    const [showRecipeForm, setShowRecipeForm] = useState(false);
    const [newRecipe, setNewRecipe] = useState({ name: '', ingredients: '' });

    const [showRunForm, setShowRunForm] = useState(false);
    const [newRun, setNewRun] = useState({ recipeId: '', lotNumber: '', quantity: 0, expiryDate: '' });

    const loadData = () => {
        fetch('/api/manufacturing?type=recipes')
            .then(r => r.json())
            .then(data => Array.isArray(data) ? setRecipes(data) : setRecipes([]))
            .catch(() => setRecipes([]));
        fetch('/api/manufacturing?type=runs')
            .then(r => r.json())
            .then(data => Array.isArray(data) ? setRuns(data) : setRuns([]))
            .catch(() => setRuns([]));
    };

    useEffect(() => { loadData(); }, []);

    const handleCreateRecipe = async (e: React.FormEvent) => {
        e.preventDefault();
        await fetch('/api/manufacturing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'recipe', data: newRecipe })
        });
        setShowRecipeForm(false);
        setNewRecipe({ name: '', ingredients: '' });
        loadData();
    };

    const handleCreateRun = async (e: React.FormEvent) => {
        e.preventDefault();
        await fetch('/api/manufacturing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'run', data: newRun })
        });
        setShowRunForm(false);
        setNewRun({ recipeId: '', lotNumber: '', quantity: 0, expiryDate: '' });
        loadData();
        alert("Production Run Created! Item added to Inventory.");
    };

    const runColumns = [
        { header: 'Date', accessor: (r: any) => formatDateTime(r.timestamp) },
        { header: 'Product', accessor: (r: any) => recipes.find(rec => rec.id === r.recipeId)?.name || r.recipeId },
        { header: 'Lot #', accessor: (r: any) => r.lotNumber },
        { header: 'Quantity', accessor: (r: any) => r.quantity },
        { header: 'Expiry', accessor: (r: any) => formatDate(r.expiryDate) },
    ];

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold text-slate-900">Media & Reagent Manufacturing</h1>

            <div className="flex gap-4 border-b border-slate-200">
                <button className={`pb-2 px-4 ${activeTab === 'runs' ? 'border-b-2 border-primary-500 font-bold text-primary-700' : 'text-slate-500'}`} onClick={() => setActiveTab('runs')}>Production Runs</button>
                <button className={`pb-2 px-4 ${activeTab === 'recipes' ? 'border-b-2 border-primary-500 font-bold text-primary-700' : 'text-slate-500'}`} onClick={() => setActiveTab('recipes')}>Recipes</button>
            </div>

            {activeTab === 'runs' && (
                <div>
                    <div className="flex justify-end mb-4">
                        <button onClick={() => setShowRunForm(!showRunForm)} className="btn-primary">
                            + Start Production Run
                        </button>
                    </div>
                    {showRunForm && (
                        <Card className="mb-6 animate-fade-in-down">
                            <form onSubmit={handleCreateRun} className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="label">Recipe</label>
                                    <select className="input-field" required value={newRun.recipeId} onChange={e => setNewRun({ ...newRun, recipeId: e.target.value })}>
                                        <option value="">-- Select Product --</option>
                                        {recipes.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className="label">Lot Number</label>
                                    <input type="text" className="input-field" required value={newRun.lotNumber} onChange={e => setNewRun({ ...newRun, lotNumber: e.target.value })} placeholder="e.g. LOT-AGAR-005" />
                                </div>
                                <div>
                                    <label className="label">Quantity Created</label>
                                    <input type="number" className="input-field" required value={newRun.quantity} onChange={e => setNewRun({ ...newRun, quantity: +e.target.value })} />
                                </div>
                                <div>
                                    <label className="label">Expiry Date</label>
                                    <input type="date" className="input-field" required value={newRun.expiryDate} onChange={e => setNewRun({ ...newRun, expiryDate: e.target.value })} />
                                </div>
                                <button type="submit" className="btn-primary col-span-2">Record Production & Add to Inventory</button>
                            </form>
                        </Card>
                    )}
                    <Card>
                        <Table data={runs} columns={runColumns} keyField="id" emptyMessage="No production runs recorded." />
                    </Card>
                </div>
            )}

            {activeTab === 'recipes' && (
                <div>
                    <div className="flex justify-end mb-4">
                        <button onClick={() => setShowRecipeForm(!showRecipeForm)} className="btn-secondary">
                            + Add Recipe
                        </button>
                    </div>
                    {showRecipeForm && (
                        <Card className="mb-6 animate-fade-in-down">
                            <form onSubmit={handleCreateRecipe} className="space-y-4">
                                <div>
                                    <label className="label">Product / Recipe Name</label>
                                    <input type="text" className="input-field" required value={newRecipe.name} onChange={e => setNewRecipe({ ...newRecipe, name: e.target.value })} />
                                </div>
                                <div>
                                    <label className="label">Ingredients (Text)</label>
                                    <textarea className="input-field" required value={newRecipe.ingredients} onChange={e => setNewRecipe({ ...newRecipe, ingredients: e.target.value })} placeholder="e.g. 50g Agar, 1L Water..." />
                                </div>
                                <button type="submit" className="btn-primary">Save Recipe</button>
                            </form>
                        </Card>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {recipes.map(recipe => (
                            <Card key={recipe.id} title={recipe.name}>
                                <p className="text-sm text-slate-600 mb-2 font-bold">Ingredients:</p>
                                <p className="text-sm text-slate-500 whitespace-pre-wrap">{recipe.ingredients}</p>
                            </Card>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
