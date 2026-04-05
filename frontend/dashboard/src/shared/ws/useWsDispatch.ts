import { useEffect } from 'react';
import { useWebSocket } from './hooks';
import { useAppDispatch } from '@/store/hooks';
import { sensorUpdated, gpsUpdated, telemetryReset } from '@/store/slices/telemetrySlice';
import { healthUpdated, healthReset } from '@/store/slices/healthSlice';
import { alertReceived, alertsReset } from '@/store/slices/alertsSlice';

/**
 * Connects to WS for a locomotive and dispatches envelope data
 * into the three Redux slices (telemetry, health, alerts).
 * Returns the connection status.
 */
export function useWsDispatch(locomotiveId: string | null) {
    const path = locomotiveId ? `/ws/live/${locomotiveId}` : null;
    const { status, subscribe } = useWebSocket(path);
    const dispatch = useAppDispatch();

    // Reset all slices when locomotive changes
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
                        gps: { latitude: number; longitude: number } | null;
                        sensors: Array<{ sensor_type: string; value: number; unit: string }>;
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
