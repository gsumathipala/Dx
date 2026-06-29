"use client";

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/Badge';

export default function MiddlewarePage() {
    const [worksheets, setWorksheets] = useState<any[]>([]);
    const [selectedWs, setSelectedWs] = useState<any>(null);
    const [simulatorLog, setSimulatorLog] = useState<string[]>([]);
    const [analyzerData, setAnalyzerData] = useState(''); // Text area for "Host Query" or "Result Output"

    useEffect(() => {
        fetch('/api/worksheets')
            .then(r => r.json())
            .then(data => Array.isArray(data) ? setWorksheets(data) : setWorksheets([]))
            .catch(() => setWorksheets([]));
    }, []);

    const addToLog = (msg: string) => setSimulatorLog(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev]);

    const handleTransmission = (direction: 'SEND' | 'RECEIVE') => {
        if (!selectedWs) return;

        if (direction === 'SEND') {
            addToLog(`Connecting to ${selectedWs.instrument}...`);
            setTimeout(() => {
                addToLog(`Sending Order Frame for Worksheet: ${selectedWs.name}`);
                // Simulate ASTM Trace
                const astm = [
                    `H|\^&|||Dx|||||||P|1`,
                    `P|1|||${selectedWs.id}||||||||`,
                    `O|1|${selectedWs.id}||^^^ALL_TESTS|R|${new Date().toISOString().replace(/-/g, '').replace(/:/g, '').replace('T', '')}|||||||||||||||||||||F`
                ].join('\n');
                setAnalyzerData(astm);
                addToLog(`Transmission Complete. 3 Frames sent.`);
            }, 800);
        }
    };

    const handleResultUpload = async () => {
        // Simulate parsing the "Analyzer Data" which user supposedly pasted from the instrument
        if (!analyzerData) {
            alert("No data received from analyzer.");
            return;
        }

        addToLog("Received Data Stream. Parsing...");

        // Mocking the result processing - in real life we parse the AST/HL7
        // For simulation, we'll just say "Success" and hypothetically update the orders. 
        // To make it real, we'd loop through lines.

        setTimeout(async () => {
            addToLog("Parsed 5 Result Records.");
            addToLog("Updating LIS Database...");

            // Call API to simulate result update (optional for this demo level, or we just alert)
            // We can just use the generic results API if we parsed simulated sample IDs correctly.

            addToLog("ACK sent. Connection Closed.");
            alert("Results imported successfully via Middleware!");
            setAnalyzerData("");
        }, 1500);
    };

    return (
        <div className="max-w-6xl space-y-6">
            <h1 className="text-2xl font-bold">Instrument Middleware Simulator</h1>
            <p className="text-slate-500">Simulate bi-directional communication with laboratory analyzers.</p>

            <div className="grid grid-cols-3 gap-6">
                {/* LEFT: Worksheet Selection */}
                <Card className="col-span-1">
                    <h2 className="font-bold mb-4">Pending Downloads</h2>
                    <div className="space-y-2 max-h-[500px] overflow-y-auto">
                        {worksheets.map(ws => (
                            <div
                                key={ws.id}
                                onClick={() => setSelectedWs(ws)}
                                className={`p-3 border rounded cursor-pointer ${selectedWs?.id === ws.id ? 'bg-blue-50 border-blue-300' : 'hover:bg-slate-50'}`}
                            >
                                <div className="font-bold text-sm">{ws.name}</div>
                                <div className="text-xs text-slate-500">{ws.instrument}</div>
                            </div>
                        ))}
                    </div>
                </Card>

                {/* MIDDLE: Simulator Console */}
                <Card className="col-span-2 flex flex-col h-[600px]">
                    <div className="flex justify-between items-center mb-4 pb-2 border-b">
                        <div>
                            <h2 className="font-bold text-lg">Connection Status: <span className="text-green-600">ONLINE</span></h2>
                            <p className="text-xs text-slate-400">Port: COM3 | Baud: 9600 | Protocol: ASTM 1394-97</p>
                        </div>
                        <div className="flex gap-2">
                            <button
                                onClick={() => handleTransmission('SEND')}
                                disabled={!selectedWs}
                                className="btn-primary"
                            >
                                📤 Send Orders
                            </button>
                            <button
                                onClick={handleResultUpload}
                                className="btn-secondary"
                            >
                                📥 Process Results
                            </button>
                        </div>
                    </div>

                    <div className="flex-1 flex flex-col gap-4">
                        {/* Data Stream Visualizer */}
                        <div className="flex-1 bg-slate-900 rounded p-4 font-mono text-xs text-green-400 overflow-y-auto">
                            <h3 className="text-slate-500 mb-1 uppercase tracking-wider text-[10px]">Data Stream (ASTM/HL7)</h3>
                            <textarea
                                className="w-full h-full bg-transparent border-none outline-none resize-none text-green-400"
                                value={analyzerData}
                                onChange={e => setAnalyzerData(e.target.value)}
                                placeholder="// Waiting for data stream..."
                            />
                        </div>

                        {/* Event Log */}
                        <div className="h-48 bg-black rounded p-2 overflow-y-auto font-mono text-xs text-slate-300 border border-slate-700">
                            {simulatorLog.map((line, i) => <div key={i}>{line}</div>)}
                            {!simulatorLog.length && <div className="text-slate-600 opacity-50">System Ready...</div>}
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    );
}
