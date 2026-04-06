import { useEffect } from 'react';
import { useWebSocket } from './hooks';
import { useAppDispatch } from '@/store/hooks';
import {
    sensorUpdated,
    gpsUpdated,
    routeNameUpdated,
    telemetryReset,
} from '@/store/slices/telemetrySlice';
import { healthUpdated, healthReset } from '@/store/slices/healthSlice';
import { alertReceived, alertsReset } from '@/store/slices/alertsSlice';

// Fans out WS envelopes into telemetry, health, and alerts slices.
export function useWsDispatch(locomotiveId: string | null) {
    const path = locomotiveId ? `/ws/live/${locomotiveId}` : null;
    const { status, subscribe } = useWebSocket(path);
    const dispatch = useAppDispatch();

    useEffect(() => {
        dispatch(telemetryReset());
        dispatch(healthReset());
        dispatch(alertsReset());
    }, [locomotiveId, dispatch]);

    useEffect(() => {
        const unsubscribe = subscribe((raw: unknown) => {
            const envelope = raw as { type?: string; data?: Record<string, unknown> };
            if (!envelope.type || !envelope.data) return;

            switch (envelope.type) {
                case 'telemetry': {
                    const reading = envelope.data as {
                        locomotive_id: string;
                        locomotive_type: string;
                        timestamp: string;
                        gps: {
                            latitude: number;
                            longitude: number;
                            bearing_deg?: number | null;
                        } | null;
                        sensors: Array<{ sensor_type: string; value: number; unit: string }>;
                        route_name?: string | null;
                    };
                    const time = new Date(reading.timestamp).getTime();
                    for (const sensor of reading.sensors) {
                        dispatch(
                            sensorUpdated({
                                sensorType: sensor.sensor_type,
                                value: sensor.value,
                                unit: sensor.unit,
                                time,
                                locomotiveType: reading.locomotive_type,
                            }),
                        );
                    }
                    if (reading.gps) {
                        dispatch(gpsUpdated(reading.gps));
                    }
                    if (reading.route_name !== undefined) {
                        dispatch(routeNameUpdated(reading.route_name ?? null));
                    }
                    break;
                }
                case 'health':
                    dispatch(healthUpdated(envelope.data as Parameters<typeof healthUpdated>[0]));
                    break;
                case 'alert':
                    dispatch(
                        alertReceived(
                            envelope.data as unknown as Parameters<typeof alertReceived>[0],
                        ),
                    );
                    break;
            }
        });

        return unsubscribe;
    }, [subscribe, dispatch]);

    return { connectionStatus: status };
}
