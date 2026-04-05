import { useCallback } from 'react';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { alertsReset } from '@/store/slices/alertsSlice';
import type { AlertEvent } from '../types';

/**
 * Returns alerts from Redux store (populated by useWsDispatch in DashboardPage).
 * No longer manages its own WS subscription.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- kept for API compatibility with consumers
export function useLiveAlerts(locomotiveId: string | null) {
    const alerts = useAppSelector((state) => state.alerts.items) as AlertEvent[];
    const dispatch = useAppDispatch();

    const clearAlerts = useCallback(() => {
        dispatch(alertsReset());
    }, [dispatch]);

    return {
        alerts,
        connectionStatus: 'connected' as const,
        clearAlerts,
    };
}
