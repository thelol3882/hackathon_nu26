import {useEffect, useState} from 'react';
import {useWebSocket} from '@/shared/ws/hooks';
import {healthApi} from '../api/healthApi';
import type {HealthIndex} from '../types';

export function useHealthIndex(locomotiveId: string | null) {
    const {
        data: restHealth,
        isLoading,
        error,
    } = healthApi.useGetHealthQuery(locomotiveId ?? '', {skip: !locomotiveId});

    const wsPath = locomotiveId ? `/ws/live/${locomotiveId}` : null;
    const {status: connectionStatus, subscribe} = useWebSocket(wsPath);

    const [liveHealth, setLiveHealth] = useState<HealthIndex | null>(null);
    const [trackedLocoId, setTrackedLocoId] = useState(locomotiveId);

    if (trackedLocoId !== locomotiveId) {
        setTrackedLocoId(locomotiveId);
        setLiveHealth(null);
    }

    useEffect(() => {
        if (!locomotiveId) return;

        const unsubscribe = subscribe((raw: unknown) => {
            const message = raw as { type?: string; data?: HealthIndex };
            if (message.type === 'health' && message.data) {
                setLiveHealth(message.data);
            }
        });

        return unsubscribe;
    }, [locomotiveId, subscribe]);

    const health = liveHealth ?? restHealth ?? null;

    return {health, isLoading, connectionStatus, error};
}
