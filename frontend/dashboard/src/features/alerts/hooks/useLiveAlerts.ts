import { useCallback, useEffect, useState } from 'react';
import { useWebSocket } from '@/shared/ws/hooks';
import type { AlertEvent } from '../types';

const MAX_ALERTS = 50;

export function useLiveAlerts(locomotiveId: string | null) {
    const path = locomotiveId ? `/ws/live/${locomotiveId}` : null;
    const { status, subscribe } = useWebSocket(path);
    const [alerts, setAlerts] = useState<AlertEvent[]>([]);

    useEffect(() => {
        const unsubscribe = subscribe((message: unknown) => {
            const msg = message as { type?: string; data?: AlertEvent };
            if (msg.type === 'alert' && msg.data) {
                setAlerts((prev) => [msg.data!, ...prev].slice(0, MAX_ALERTS));
            }
        });

        return unsubscribe;
    }, [subscribe]);

    const clearAlerts = useCallback(() => {
        setAlerts([]);
    }, []);

    return {
        alerts,
        connectionStatus: status,
        clearAlerts,
    };
}
