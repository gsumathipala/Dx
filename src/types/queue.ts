export interface AuthorizationQueue {
    id: string;
    name: string;
    description: string;
    createdBy: string;
    createdAt: string;
}

export interface RecordLock {
    id: string;
    recordType: 'order' | 'result' | 'patient';
    recordId: string;
    userId: string;
    userName: string;
    lockedAt: string;
    expiresAt: string;
}

export interface QueueHistoryEntry {
    timestamp: string;
    fromQueueId?: string;
    fromQueueName?: string;
    toQueueId: string;
    toQueueName: string;
    movedBy: string;
}
