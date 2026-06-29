'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function MobileCollections() {
    const [orders, setOrders] = useState<any[]>([]);
    const router = useRouter();

    useEffect(() => {
        fetch('/api/mobile/collections')
            .then(res => res.json())
            .then(data => Array.isArray(data) ? setOrders(data) : setOrders([]))
            .catch(() => setOrders([]));
    }, []);

    const handleCollect = async (orderId: string) => {
        if (!confirm('Confirm Collection?')) return;

        await fetch('/api/mobile/collections', {
            method: 'POST',
            body: JSON.stringify({ orderId }),
            headers: { 'Content-Type': 'application/json' }
        });

        // Refresh
        setOrders(prev => prev.filter(o => o.orderId !== orderId));
    };

    return (
        <div className="min-h-screen bg-gray-100 p-4">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold text-gray-800">Phlebotomy Worklist</h1>
                <button onClick={() => router.push('/dashboard')} className="text-sm text-blue-600">Exit to Dashboard</button>
            </div>

            <div className="grid gap-4">
                {orders.map((order) => (
                    <div key={order.orderId} className="bg-white p-6 rounded-xl shadow-md flex justify-between items-center border-l-8 border-blue-500">
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="text-lg font-bold">{order.accessionNumber}</span>
                                {order.priority === 'Stat' && <span className="bg-red-100 text-red-800 text-xs px-2 py-1 rounded font-bold uppercase">STAT</span>}
                            </div>
                            <p className="text-gray-600 text-lg">{order.patientName} ({order.patientMrn})</p>
                            <p className="text-xs text-gray-400 mt-1">Tests: {JSON.parse(order.testIds || '[]').join(', ')}</p>
                        </div>

                        <button
                            onClick={() => handleCollect(order.orderId)}
                            className="bg-green-600 hover:bg-green-700 text-white font-bold h-16 w-32 rounded-lg text-xl shadow"
                        >
                            Collect
                        </button>
                    </div>
                ))}
                {orders.length === 0 && (
                    <p className="text-center text-gray-500 mt-10">No pending collections.</p>
                )}
            </div>
        </div>
    );
}
