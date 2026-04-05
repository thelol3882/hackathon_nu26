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

/**
 * Connects to /ws/fleet and dispatches fleet summary + changes
 * into the fleet Redux slice.
 *
 * The WS server sends two envelope types:
 *   fleet_summary — full fleet stats every ~2 seconds
 *   fleet_changes — only locomotives that changed health category
 */
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
