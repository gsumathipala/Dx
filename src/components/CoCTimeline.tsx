"use client";

import React, { useState, useEffect } from 'react';
import type { CoCEvent, CoCTimeline as CoCTimelineType } from '@/types/coc-event';
import { getCoCEventLabel, getCoCEventColor } from '@/types/coc-event';
import { formatDateTime } from '@/lib/utils';

interface CoCTimelineProps {
    sampleId?: string;
    accessionNumber?: string;
    autoRefresh?: boolean;
    refreshInterval?: number; // milliseconds
}

export function CoCTimeline({
    sampleId,
    accessionNumber,
    autoRefresh = false,
    refreshInterval = 30000
}: CoCTimelineProps) {
    const [timeline, setTimeline] = useState<CoCTimelineType | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadTimeline = async () => {
        if (!sampleId && !accessionNumber) {
            setError('Sample ID or Accession Number required');
            setLoading(false);
            return;
        }

        try {
            const params = new URLSearchParams();
            if (sampleId) params.set('sampleId', sampleId);
            if (accessionNumber) params.set('accessionNumber', accessionNumber);

            const res = await fetch(`/api/coc?${params.toString()}`);
            if (!res.ok) throw new Error('Failed to load CoC timeline');

            const data = await res.json();
            setTimeline(data);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadTimeline();

        if (autoRefresh) {
            const interval = setInterval(loadTimeline, refreshInterval);
            return () => clearInterval(interval);
        }
    }, [sampleId, accessionNumber, autoRefresh, refreshInterval]);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                <p className="font-semibold">Error loading Chain of Custody</p>
                <p className="text-sm">{error}</p>
            </div>
        );
    }

    if (!timeline || timeline.events.length === 0) {
        return (
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center text-slate-500">
                <p>No Chain of Custody events recorded yet.</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                <div className="flex justify-between items-start">
                    <div>
                        <h3 className="font-bold text-slate-900">Chain of Custody Timeline</h3>
                        <p className="text-sm text-slate-600">Accession: {timeline.accessionNumber}</p>
                    </div>
                    <div className="text-right">
                        <p className="text-sm text-slate-600">Current Location</p>
                        <p className="font-semibold text-slate-900">{timeline.currentLocation || 'Unknown'}</p>
                    </div>
                </div>
            </div>

            {/* Timeline */}
            <div className="relative">
                {/* Vertical line */}
                <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-slate-200"></div>

                {/* Events */}
                <div className="space-y-6">
                    {timeline.events.map((event, index) => (
                        <CoCEventCard
                            key={event.id}
                            event={event}
                            isLatest={index === timeline.events.length - 1}
                        />
                    ))}
                </div>
            </div>
        </div>
    );
}

interface CoCEventCardProps {
    event: CoCEvent;
    isLatest: boolean;
}

function CoCEventCard({ event, isLatest }: CoCEventCardProps) {
    const color = getCoCEventColor(event.eventType);
    const label = getCoCEventLabel(event.eventType);

    const colorClasses = {
        blue: 'bg-blue-100 border-blue-300 text-blue-700',
        green: 'bg-green-100 border-green-300 text-green-700',
        purple: 'bg-purple-100 border-purple-300 text-purple-700',
        orange: 'bg-orange-100 border-orange-300 text-orange-700',
        gray: 'bg-gray-100 border-gray-300 text-gray-700',
        cyan: 'bg-cyan-100 border-cyan-300 text-cyan-700',
        red: 'bg-red-100 border-red-300 text-red-700'
    };

    const dotColorClasses = {
        blue: 'bg-blue-500',
        green: 'bg-green-500',
        purple: 'bg-purple-500',
        orange: 'bg-orange-500',
        gray: 'bg-gray-500',
        cyan: 'bg-cyan-500',
        red: 'bg-red-500'
    };

    return (
        <div className="relative pl-16">
            {/* Dot on timeline */}
            <div className={`absolute left-4 top-2 w-5 h-5 rounded-full border-4 border-white ${dotColorClasses[color as keyof typeof dotColorClasses]} ${isLatest ? 'ring-4 ring-blue-200' : ''}`}></div>

            {/* Event card */}
            <div className={`border rounded-lg p-4 ${isLatest ? 'bg-white shadow-md' : 'bg-slate-50'}`}>
                <div className="flex justify-between items-start mb-2">
                    <div>
                        <span className={`inline-block px-2 py-1 rounded text-xs font-semibold border ${colorClasses[color as keyof typeof colorClasses]}`}>
                            {label}
                        </span>
                        {isLatest && (
                            <span className="ml-2 inline-block px-2 py-1 rounded text-xs font-semibold bg-blue-100 border border-blue-300 text-blue-700">
                                Current
                            </span>
                        )}
                    </div>
                    <p className="text-xs text-slate-500">{formatDateTime(event.timestamp)}</p>
                </div>

                <div className="space-y-1 text-sm">
                    <p className="text-slate-700">
                        <span className="font-semibold">Performed by:</span> {event.performedByName} ({event.performedBy})
                    </p>

                    {event.location && (
                        <p className="text-slate-700">
                            <span className="font-semibold">Location:</span> {event.location}
                        </p>
                    )}

                    {event.fromLocation && event.toLocation && (
                        <p className="text-slate-700">
                            <span className="font-semibold">Transfer:</span> {event.fromLocation} → {event.toLocation}
                        </p>
                    )}

                    {event.notes && (
                        <p className="text-slate-600 italic">
                            <span className="font-semibold">Notes:</span> {event.notes}
                        </p>
                    )}

                    {event.signature && (
                        <p className="text-xs text-slate-400 font-mono mt-2">
                            Signature: {event.signature.substring(0, 16)}...
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
}
