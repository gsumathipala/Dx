"use client";

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { formatDateTime } from '@/lib/utils';
import { useReactToPrint } from 'react-to-print';
import { PatientReport } from '@/components/reports/PatientReport';
import { CoaReport } from '@/components/reports/CoaReport';
import { Card } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';

// Wrapper component to use searchParams safely
function ResultsPageContent() {
    const { user } = useAuth();
    const componentRef = useRef<HTMLDivElement>(null);
    const coaRef = useRef<HTMLDivElement>(null);

    const [orders, setOrders] = useState<any[]>([]);
    const [tests, setTests] = useState<any[]>([]);
    const [inventory, setInventory] = useState<any[]>([]);
    const [cannedComments, setCannedComments] = useState<any[]>([]);
    const [filteredOrders, setFilteredOrders] = useState<any[]>([]);
    const [queues, setQueues] = useState<any[]>([]);

    const [selectedOrder, setSelectedOrder] = useState<any>(null);
    const [filterTestId, setFilterTestId] = useState<string>('');

    const [resultValues, setResultValues] = useState<Record<string, string>>({});
    const [attachments, setAttachments] = useState<Record<string, string>>({});
    const [lotNumbers, setLotNumbers] = useState<Record<string, string>>({});
    const [reportNotes, setReportNotes] = useState('');
    const [internalComments, setInternalComments] = useState('');

    // Queue and Locking State
    const [currentQueue, setCurrentQueue] = useState<string | null>(null);
    const [lockStatus, setLockStatus] = useState<any>(null);
    const [isLocked, setIsLocked] = useState(false);

    // LP-1 Validation & ISO Standards: Only Manager/Admin can release final results.
    const canValidate = ['admin', 'manager'].includes(user?.role || '');
    const canManageQueues = ['admin', 'manager'].includes(user?.role || '');
    const isMedic = user?.role === 'medic';
    const isScientist = user?.role === 'scientist';
    const searchParams = useSearchParams();

    const loadData = async () => {
        try {
            const [ordersRes, testsRes, invRes, commentsRes, queuesRes] = await Promise.all([
                fetch('/api/orders').then(r => r.ok ? r.json() : []),
                fetch('/api/admin/tests').then(r => r.ok ? r.json() : []),
                fetch('/api/inventory').then(r => r.ok ? r.json() : []),
                fetch('/api/admin/comments').then(r => r.ok ? r.json() : []),
                fetch('/api/queues').then(r => r.ok ? r.json() : [])
            ]);

            const sorted = ordersRes.sort((a: any, b: any) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
            setOrders(sorted);
            setTests(testsRes);
            setInventory(invRes || []);
            setCannedComments(commentsRes || []);
            setQueues(queuesRes || []);
        } catch (error) {
            console.error('Failed to load data:', error);
        }
    };

    useEffect(() => { loadData(); }, []);
    useEffect(() => {
        if (filterTestId) setFilteredOrders(orders.filter(o => o.testIds?.includes(filterTestId)));
        else setFilteredOrders(orders);
    }, [filterTestId, orders]);
    // Deep link support: auto-select order from URL query param
    useEffect(() => {
        const orderId = searchParams.get('orderId');
        if (orderId && orders.length > 0 && !selectedOrder) {
            const order = orders.find(o => o.id === orderId);
            if (order) handleSelectOrder(order);
        }
    }, [searchParams, orders]);

    const handleSelectOrder = async (order: any) => {
        setSelectedOrder(order);
        setCurrentQueue(order.queueId || null);
        setResultValues({});
        setAttachments({});
        setLotNumbers({});
        setReportNotes('');
        setInternalComments('');

        // Initial lock check is handled by the useEffect above

        const res = await fetch(`/api/results?orderId=${order.id}`);
        const existing = await res.json();
        if (existing && existing.length > 0) {
            const latest = existing[0];
            setResultValues(latest.values?.results || {});
            setAttachments(latest.values?.attachments || {});
            setLotNumbers(latest.values?.lotNumbers || {});
            setReportNotes(latest.values?.notes || '');
            setInternalComments(latest.values?.internalComments || '');
        }
    };

    const checkCheckoutStatus = async (orderId: string) => {
        try {
            const res = await fetch(`/api/locks?recordType=order&recordId=${orderId}`);
            if (res.ok) {
                const data = await res.json();
                setLockStatus(data.locked ? data.lock : null);
                setIsLocked(data.locked && data.lock?.userId !== user?.username);
            }
        } catch (err) {
            console.error('Failed to check checkout status:', err);
        }
    };

    // Force check-in (Admin only)
    const handleForceCheckin = async () => {
        if (!selectedOrder) return;

        const reason = prompt('Enter reason for force check-in (required):');
        if (!reason || !reason.trim()) {
            alert('Reason is required for force check-in');
            return;
        }

        if (!confirm('Force check in this record? Original user will lose their checkout.')) {
            return;
        }

        try {
            const res = await fetch('/api/locks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'force-checkin',
                    recordType: 'order',
                    recordId: selectedOrder.id,
                    reason
                })
            });

            if (res.ok) {
                setLockStatus(null);
                setIsLocked(false);
                await checkCheckoutStatus(selectedOrder.id);
                alert('Record forcibly checked in');
            } else {
                const data = await res.json();
                alert(data.error || 'Failed to force check in');
            }
        } catch (err) {
            console.error('Failed to force checkin:', err);
            alert('Failed to force check in');
        }
    };

    // Auto-Lock & Heartbeat Logic
    useEffect(() => {
        if (!selectedOrder) return;

        const acquireLock = async () => {
            try {
                // First check if already locked
                const checkRes = await fetch(`/api/locks?recordType=order&recordId=${selectedOrder.id}`);
                const checkData = await checkRes.json();

                if (checkData.locked && checkData.lock.userId !== user?.username) {
                    // Locked by someone else
                    setLockStatus(checkData.lock);
                    setIsLocked(true);
                } else {
                    // Try to acquire/extend lock
                    const res = await fetch('/api/locks', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            action: 'checkout',
                            recordType: 'order',
                            recordId: selectedOrder.id,
                            reason: 'Auto-lock for editing'
                        })
                    });

                    if (res.ok) {
                        const data = await res.json();
                        setLockStatus(data.checkout);
                        setIsLocked(false);
                    } else if (res.status === 409) {
                        const data = await res.json();
                        setLockStatus(data.checkout);
                        setIsLocked(true);
                    }
                }
            } catch (err) {
                console.error('Lock error:', err);
            }
        };

        // Initial lock attempt
        acquireLock();

        // Heartbeat every 30 seconds to keep lock alive
        const heartbeatInterval = setInterval(acquireLock, 30000);

        // Cleanup: Unlock when unmounting or switching orders
        return () => {
            clearInterval(heartbeatInterval);
            if (!isLocked) { // Only unlock if we actually hold the lock
                fetch('/api/locks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: 'checkin',
                        recordType: 'order',
                        recordId: selectedOrder.id
                    })
                }).catch(console.error);
            }
        };
    }, [selectedOrder, user?.username]);

    const handleSave = async (status: 'Preliminary' | 'Pending Validation' | 'Completed', auditOverride?: { action: string, details: string }) => {
        if (!selectedOrder) return;

        // Prevent Medics from editing
        if (isMedic) {
            alert("Access Denied: Medics cannot edit results.");
            return;
        }

        // Validation Logic
        if (status === 'Pending Validation' && !auditOverride) {
            const confirmMsg = "Submit for Supervisor Review? (LP-1)";
            if (!confirm(confirmMsg)) return;
        }

        if (status === 'Completed' && !auditOverride) {
            if (!canValidate) {
                alert("Permission Denied: Only Lab Managers or Admins can Finalize results.\nPlease submit for Validation.");
                status = 'Pending Validation'; // Force downgrade status
            } else {
                // Traceability Check (ISO 15189)
                for (const testId of selectedOrder.testIds || []) {
                    if (!lotNumbers[testId]) {
                        alert('Traceability Error: Reagent Lot Number required for Final Release.');
                        return;
                    }
                }
            }
        }

        // Auto-assign to pending-technical queue when submitting for tech validation
        let queueToSet = currentQueue;
        if (status === 'Pending Validation') {
            queueToSet = 'pending-technical';
        } else if (status === 'Completed') {
            queueToSet = 'completed'; // Move to completed queue when verified
        }

        const payload = {
            orderId: selectedOrder.id,
            status,
            performedBy: user?.username,
            values: { results: resultValues, attachments, lotNumbers, notes: reportNotes, internalComments },
            queueId: queueToSet,
            auditAction: auditOverride?.action,
            auditDetails: auditOverride?.details
        };

        const res = await fetch('/api/results', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            loadData();
            // Refresh logic - re-select the order to update audit trail from server
            const updatedOrders = await fetch('/api/orders').then(r => r.json());
            setOrders(updatedOrders);
            const freshOrder = updatedOrders.find((o: any) => o.id === selectedOrder.id);
            if (freshOrder) setSelectedOrder(freshOrder);

            if (status === 'Completed' && !auditOverride) setSelectedOrder(null);
            else if (!auditOverride) {
                alert(`Status updated to: ${status}`);
            }
        }
    };

    const handleCustodyAction = async (action: string) => {
        // Log immediately to Audit Trail
        const details = `${action} by ${user?.username}`;
        // Update local comment for visibility
        setInternalComments(prev => `[${formatDateTime(new Date().toISOString())}] Custody: ${details}\n` + prev);

        // Save using current status but with Override
        await handleSave(selectedOrder.status as any || 'Preliminary', { action: 'CUSTODY_LOG', details });
        alert(`Custody Action Logged: ${action}`);
    };

    const handlePrint = useReactToPrint({
        contentRef: componentRef,
        documentTitle: `Report_${selectedOrder?.accessionNumber}`,
    });

    const handlePrintCoa = useReactToPrint({
        contentRef: coaRef,
        documentTitle: `COA_${selectedOrder?.accessionNumber}`,
    });

    return (
        <div className="flex gap-6 min-h-[500px]">
            <div className="w-1/3 flex flex-col gap-4">
                <Card className="flex-1 flex flex-col p-0 overflow-hidden">
                    <div className="p-4 border-b bg-slate-50">
                        <h2 className="font-bold text-lg mb-2 text-slate-800">Worklist</h2>
                        <select className="w-full border p-2 rounded text-sm text-slate-700" value={filterTestId} onChange={e => setFilterTestId(e.target.value)}>
                            <option value="">All Tests</option>
                            {tests.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                        </select>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                        {filteredOrders.map(order => {
                            // Get test names for this order
                            const orderTests = (order.testIds || [])
                                .map((tid: string) => tests.find(t => t.id === tid)?.name || tid)
                                .slice(0, 3); // Show first 3 tests
                            const moreTests = (order.testIds || []).length - 3;

                            return (
                                <div
                                    key={order.id}
                                    onClick={() => handleSelectOrder(order)}
                                    className={`p-4 rounded-lg border cursor-pointer transition-all ${selectedOrder?.id === order.id
                                        ? 'bg-primary-50 ring-2 ring-primary-500 border-primary-300'
                                        : 'bg-white hover:bg-slate-50 hover:border-slate-300'
                                        }`}
                                >
                                    {/* Header: Accession & Status */}
                                    <div className="flex justify-between items-center mb-2">
                                        <span className="font-bold text-slate-800 font-mono">{order.accessionNumber}</span>
                                        <StatusBadge status={order.status} />
                                    </div>

                                    {/* Patient Info */}
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="text-lg">👤</span>
                                        <div>
                                            <p className="text-sm font-semibold text-slate-700">
                                                {order.patientName || 'Unknown Patient'}
                                            </p>
                                            {order.patientDob && (
                                                <p className="text-xs text-slate-400">
                                                    DOB: {order.patientDob}
                                                </p>
                                            )}
                                        </div>
                                    </div>

                                    {/* Specimen Info */}
                                    {order.specimenType && (
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="text-sm">🧫</span>
                                            <span className="text-xs text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                                                {order.specimenType}
                                            </span>
                                            {order.priority === 'STAT' && (
                                                <span className="text-xs text-red-600 bg-red-100 px-2 py-0.5 rounded font-bold">
                                                    ⚡ STAT
                                                </span>
                                            )}
                                        </div>
                                    )}

                                    {/* Tests Ordered */}
                                    <div className="flex items-start gap-2">
                                        <span className="text-sm mt-0.5">🧪</span>
                                        <div className="flex flex-wrap gap-1">
                                            {orderTests.map((testName: string, idx: number) => (
                                                <span
                                                    key={idx}
                                                    className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded"
                                                >
                                                    {testName}
                                                </span>
                                            ))}
                                            {moreTests > 0 && (
                                                <span className="text-xs text-slate-400 px-1">
                                                    +{moreTests} more
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    {/* Timestamp */}
                                    <div className="mt-2 pt-2 border-t border-slate-100 text-xs text-slate-400 flex justify-between">
                                        <span>{formatDateTime(order.timestamp)}</span>
                                        {order.collectedAt && (
                                            <span>Collected: {formatDateTime(order.collectedAt)}</span>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                        {filteredOrders.length === 0 && (
                            <div className="p-8 text-center text-slate-400 italic">
                                No orders found
                            </div>
                        )}
                    </div>
                </Card>
            </div>

            <div className="flex-1 flex flex-col overflow-hidden">
                {selectedOrder ? (
                    <Card className="flex-1 flex flex-col overflow-hidden p-0">
                        <div className="p-6 border-b bg-slate-50">
                            <div className="flex justify-between items-start mb-4">
                                <div>
                                    <h1 className="text-2xl font-bold mb-1 text-slate-900">Result Entry</h1>
                                    <p className="text-slate-600">Accession: <span className="font-mono font-bold text-slate-800">{selectedOrder.accessionNumber}</span></p>
                                </div>
                                <div className="flex gap-2">
                                    <button onClick={() => handleCustodyAction("Retrieved from Storage")} className="btn-secondary text-xs" disabled={isLocked}>📦 Retrieve</button>
                                    <button onClick={() => handleCustodyAction("Returned to Storage")} className="btn-secondary text-xs" disabled={isLocked}>📥 Return</button>
                                    <button onClick={() => handleCustodyAction("Disposed")} className="bg-red-100 text-red-700 hover:bg-red-200 px-3 py-1 rounded text-xs font-bold" disabled={isLocked}>🗑️ Dispose</button>

                                    {selectedOrder.status === 'Completed' && (
                                        <>
                                            <button onClick={() => handlePrint()} className="btn-secondary flex items-center gap-2">🖨️ Patient Report</button>
                                            <button onClick={() => handlePrintCoa()} className="btn-secondary flex items-center gap-2 border-slate-600 text-slate-800">🎖️ Cert. of Analysis</button>
                                        </>
                                    )}
                                </div>
                            </div>

                            {/* Lock Status Indicators */}
                            {isLocked && lockStatus ? (
                                <div className="mb-4 p-3 bg-red-50 border-l-4 border-red-500 rounded flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className="text-red-500 text-xl">🔒</span>
                                        <div>
                                            <p className="font-bold text-red-900 text-sm">Editing Locked</p>
                                            <p className="text-xs text-red-700">
                                                Currently being edited by <strong>{lockStatus.userName}</strong>. You are in <strong>Read-Only</strong> mode.
                                            </p>
                                        </div>
                                    </div>
                                    {canValidate && (
                                        <button
                                            onClick={handleForceCheckin}
                                            className="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 text-xs font-bold"
                                        >
                                            Force Unlock
                                        </button>
                                    )}
                                </div>
                            ) : (
                                <div className="mb-4 p-2 bg-green-50 border border-green-200 rounded flex items-center gap-2 text-xs text-green-800">
                                    <span className="text-green-600">✏️</span>
                                    <span>
                                        You are editing this record. It is locked for others until you leave.
                                    </span>
                                </div>
                            )}

                            {/* Queue Assignment */}
                            {canManageQueues && (
                                <div className="flex items-center gap-4">
                                    <label className="text-sm font-semibold text-slate-700">Authorization Queue:</label>
                                    <select
                                        value={currentQueue || ''}
                                        onChange={(e) => setCurrentQueue(e.target.value || null)}
                                        className="px-4 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                                        disabled={isLocked}
                                    >
                                        <option value="">Unassigned</option>
                                        {queues.map((q: any) => (
                                            <option key={q.id} value={q.id}>{q.name}</option>
                                        ))}
                                    </select>
                                    {selectedOrder.queueId && selectedOrder.queueId !== currentQueue && (
                                        <span className="text-xs text-amber-600 italic">Queue will change on save</span>
                                    )}
                                </div>
                            )}
                        </div>

                        <div className="flex-1 overflow-y-auto p-6 space-y-8">
                            {/* Validation Alert */}
                            {selectedOrder.status === 'Pending Validation' && (
                                <div className="bg-amber-50 border-l-4 border-amber-500 p-4 mb-4">
                                    <p className="font-bold text-amber-700">⚠️ Needs Supervisor Review</p>
                                    <p className="text-sm text-amber-600">This order is waiting for validation (LP-1). Review results and finalize.</p>
                                </div>
                            )}

                            {(selectedOrder.testIds || []).map((testId: string) => {
                                const testDef = tests.find(t => t.id === testId);
                                if (!testDef) return null;

                                // Access Control: Read Only if not Admin and not in same department
                                const isCrossDept = user?.role !== 'admin' && user?.department && testDef.department && user.department !== testDef.department;
                                const isReadOnly = isMedic || isLocked || (selectedOrder.status === 'Completed' && !canValidate) || isCrossDept;
                                const value = resultValues[testId];
                                let flag = '';
                                let flagClass = '';
                                let flagBg = '';

                                if (value && testDef.referenceRange) {
                                    const range = testDef.referenceRange;
                                    const numVal = parseFloat(value);

                                    if (!isNaN(numVal)) {
                                        const min = typeof range === 'object' ? range.min : parseFloat((range as string).split('-')[0]);
                                        const max = typeof range === 'object' ? range.max : parseFloat((range as string).split('-')[1]);
                                        const panicLow = typeof range === 'object' ? range.panicLow : null;
                                        const panicHigh = typeof range === 'object' ? range.panicHigh : null;

                                        if (panicLow && numVal <= panicLow) {
                                            flag = '⚠️ PANIC LOW';
                                            flagClass = 'text-white font-bold';
                                            flagBg = 'bg-red-600';
                                        } else if (panicHigh && numVal >= panicHigh) {
                                            flag = '⚠️ PANIC HIGH';
                                            flagClass = 'text-white font-bold';
                                            flagBg = 'bg-red-600';
                                        } else if (min && numVal < min) {
                                            flag = '↓ Low';
                                            flagClass = 'text-blue-700 font-bold';
                                            flagBg = 'bg-blue-100';
                                        } else if (max && numVal > max) {
                                            flag = '↑ High';
                                            flagClass = 'text-orange-700 font-bold';
                                            flagBg = 'bg-orange-100';
                                        } else {
                                            flag = '✓ Normal';
                                            flagClass = 'text-green-700';
                                            flagBg = 'bg-green-50';
                                        }
                                    }
                                }

                                const rangeText = testDef.referenceRange
                                    ? (typeof testDef.referenceRange === 'object'
                                        ? testDef.referenceRange.text || `${testDef.referenceRange.min}-${testDef.referenceRange.max}`
                                        : testDef.referenceRange)
                                    : 'N/A';

                                return (
                                    <div key={testId} className={`border rounded-lg p-5 ${flag.includes('PANIC') ? 'border-red-500 border-2 bg-red-50' : 'border-slate-200 bg-slate-50/50'}`}>
                                        <div className="flex justify-between items-center border-b border-slate-200 pb-3 mb-4">
                                            <div>
                                                <h3 className="font-bold text-lg text-primary-800">{testDef.name}</h3>
                                                {testDef.loincCode && (
                                                    <span className="text-xs text-slate-400">LOINC: {testDef.loincCode}</span>
                                                )}
                                                {isCrossDept && <span className="ml-2 text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded border">Read Only ({testDef.department})</span>}
                                            </div>
                                            <select className="border rounded p-1 text-xs bg-white text-slate-900" value={lotNumbers[testId] || ''} onChange={e => setLotNumbers({ ...lotNumbers, [testId]: e.target.value })}>
                                                <option value="">-- Reagent Lot (Traceable) --</option>
                                                {inventory.map(item => <option key={item.id} value={item.lotNumber}>{item.name} ({item.lotNumber})</option>)}
                                            </select>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <input
                                                type="text"
                                                className={`input-field text-lg font-medium flex-1 ${flag.includes('PANIC') ? 'border-red-500 border-2' : ''}`}
                                                value={resultValues[testId] || ''}
                                                onChange={e => setResultValues({ ...resultValues, [testId]: e.target.value })}
                                                disabled={isReadOnly}
                                                title={isCrossDept ? `Read Only (${testDef.department || 'Other'} Dept)` : ''}
                                            />
                                            <span className="text-slate-500 font-medium">{testDef.units}</span>
                                            {flag && (
                                                <span className={`px-3 py-1 rounded-full text-sm ${flagBg} ${flagClass}`}>
                                                    {flag}
                                                </span>
                                            )}
                                        </div>
                                        <div className="mt-2 text-xs text-slate-500">
                                            Reference Range: <span className="font-mono">{rangeText} {testDef.units}</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Canned Comments Section */}
                        <div className="px-6 py-2 bg-slate-50 border-t border-slate-200">
                            <div className="flex items-center gap-2 mb-2">
                                <label className="text-xs font-bold uppercase text-slate-500">Quick Insert (Coded Comment):</label>
                                <select
                                    className="border rounded p-1 text-sm text-slate-700 w-64"
                                    onChange={(e) => {
                                        if (e.target.value) {
                                            setReportNotes(prev => prev + (prev ? '\n' : '') + e.target.value);
                                            e.target.value = ""; // Reset dropdown
                                        }
                                    }}
                                >
                                    <option value="">-- Select Code --</option>
                                    {cannedComments.map((c: any) => (
                                        <option key={c.code} value={c.text}>{c.code} - {c.text}</option>
                                    ))}
                                </select>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <textarea className="input-field h-24 text-sm bg-purple-50" placeholder="Internal Custody/Lab Notes... (Private)" value={internalComments} onChange={e => setInternalComments(e.target.value)} />
                                <div className="space-y-1">
                                    <textarea className="input-field h-24 text-sm font-mono" placeholder="Public Report Notes... (Appears on Patient Report)" value={reportNotes} onChange={e => setReportNotes(e.target.value)} />
                                    <p className="text-[10px] text-slate-400 text-right">Use the dropdown above to insert standard phrases.</p>
                                </div>
                            </div>

                            {/* Sample Audit Trail UI */}
                            {selectedOrder.auditTrail && selectedOrder.auditTrail.length > 0 && (
                                <div className="mt-6 border-t pt-4">
                                    <h4 className="text-xs font-bold uppercase text-slate-500 mb-2">Sample Audit Trail (Permanent)</h4>
                                    <div className="max-h-32 overflow-y-auto border rounded bg-white text-xs">
                                        <table className="w-full text-left">
                                            <thead>
                                                <tr className="bg-slate-100 border-b">
                                                    <th className="p-2">Timestamp</th>
                                                    <th className="p-2">User</th>
                                                    <th className="p-2">Action</th>
                                                    <th className="p-2">Details</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {(Array.isArray(selectedOrder.auditTrail) ? selectedOrder.auditTrail : []).slice().reverse().map((log: any, i: number) => (
                                                    <tr key={i} className="border-b last:border-0 hover:bg-slate-50">
                                                        <td className="p-2 font-mono text-slate-500">{formatDateTime(log.timestamp)}</td>
                                                        <td className="p-2 font-bold">{log.user}</td>
                                                        <td className="p-2"><span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-bold">{log.action}</span></td>
                                                        <td className="p-2 text-slate-600">{log.details}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="p-6 border-t bg-slate-50 flex gap-4 justify-between items-center">
                            {/* Verification Status Display */}
                            <div className="text-xs text-slate-500">
                                {selectedOrder.status === 'Completed' && (
                                    <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full font-bold">✓ Clinically Verified</span>
                                )}
                                {selectedOrder.status === 'Pending Validation' && (
                                    <span className="px-3 py-1 bg-amber-100 text-amber-700 rounded-full font-bold">⏳ Pending Technical Validation</span>
                                )}
                                {selectedOrder.status === 'Technically Validated' && (
                                    <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full font-bold">📋 Pending Clinical Verification</span>
                                )}
                            </div>

                            <div className="flex gap-4">
                                {!isMedic && !isLocked && (
                                    <>
                                        {/* Save Draft - Available to scientists */}
                                        <button
                                            onClick={() => handleSave('Preliminary')}
                                            className="btn-secondary"
                                            disabled={isLocked}
                                        >
                                            Save Draft
                                        </button>

                                        {/* Level 1: Technical Validation - Scientists and up */}
                                        {selectedOrder.status !== 'Completed' && selectedOrder.status !== 'Technically Validated' && (
                                            <button
                                                onClick={() => handleSave('Pending Validation')}
                                                className="bg-amber-100 text-amber-800 hover:bg-amber-200 px-4 py-2 rounded font-bold transition-colors"
                                            >
                                                📝 Submit for Tech Validation
                                            </button>
                                        )}
                                    </>
                                )}

                                {/* Level 2: Clinical Verification - Verifiers, Managers, Admins only */}
                                {/* MUST be a different user than who did L1 */}
                                {['admin', 'manager', 'medic'].includes(user?.role || '') &&
                                    (selectedOrder.status === 'Pending Validation' || selectedOrder.status === 'Technically Validated') && (
                                        <button
                                            onClick={() => {
                                                if (!confirm('Clinically verify these results? This will release them for reporting.')) return;
                                                handleSave('Completed');
                                            }}
                                            className="btn-primary shadow-lg"
                                        >
                                            ✓ Clinical Verify & Release
                                        </button>
                                    )}

                                {/* Print buttons - ONLY if clinically verified */}
                                {selectedOrder.status === 'Completed' && (
                                    <>
                                        <button onClick={() => handlePrint()} className="btn-secondary">
                                            🖨️ Print Patient Report
                                        </button>
                                        <button onClick={() => handlePrintCoa()} className="btn-secondary">
                                            📄 Print COA
                                        </button>
                                    </>
                                )}

                                {/* Block printing if not verified */}
                                {selectedOrder.status !== 'Completed' && (
                                    <button
                                        disabled
                                        className="px-4 py-2 bg-gray-200 text-gray-400 rounded cursor-not-allowed"
                                        title="Report cannot be printed until clinically verified"
                                    >
                                        🔒 Print (Pending Verification)
                                    </button>
                                )}
                            </div>
                        </div>

                        <div style={{ display: 'none' }}>
                            <PatientReport ref={componentRef} order={selectedOrder} results={{ results: resultValues, notes: reportNotes, performedBy: user?.username }} tests={tests} />
                            <CoaReport ref={coaRef} order={selectedOrder} results={{ results: resultValues }} tests={tests} />
                        </div>
                    </Card>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center p-8 text-slate-400 bg-slate-50 border-2 border-dashed border-slate-200 rounded-lg m-4">
                        <div className="text-6xl mb-4">🧪</div>
                        <p className="text-lg font-medium text-slate-500">Select an order</p>
                    </div>
                )}
            </div>
        </div >
    );
}

// Wrap the component with Suspense for useSearchParams
export default function ResultsPage() {
    return (
        <Suspense fallback={<div className="p-8 text-slate-400">Loading...</div>}>
            <ResultsPageContent />
        </Suspense>
    );
}
