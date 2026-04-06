import { useEffect } from 'react';
import { useWebSocket } from './hooks';
import { useAppDispatch } from '@/store/hooks';
import {
    fleetSummaryUpdated,
    fleetChangesReceived,
    fleetReset,
    type FleetSummaryPayload,
    type FleetChangesPayload,
} from '@/store/slices/fleetSlice';

// Envelope types: fleet_summary (full stats, ~2s) and fleet_changes (deltas only).
export function useFleetDispatch() {
    const { status, subscribe } = useWebSocket('/ws/fleet');
    const dispatch = useAppDispatch();

    useEffect(() => {
        dispatch(fleetReset());
    }, [dispatch]);

    useEffect(() => {
        const unsubscribe = subscribe((raw: unknown) => {
            const envelope = raw as { type?: string; data?: Record<string, unknown> };
            if (!envelope.type || !envelope.data) return;

            switch (envelope.type) {
                case 'fleet_summary':
                    dispatch(fleetSummaryUpdated(envelope.data as unknown as FleetSummaryPayload));
                    break;
                case 'fleet_changes':
                    dispatch(fleetChangesReceived(envelope.data as unknown as FleetChangesPayload));
                    break;
            }
        });

        return unsubscribe;
    }, [subscribe, dispatch]);

    return { connectionStatus: status };
}
