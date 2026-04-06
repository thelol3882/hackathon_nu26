import { useMemo } from 'react';
import { useAppSelector } from '@/store/hooks';
import type { SensorType, TelemetryReading } from '../types';

interface Position {
    latitude: number;
    longitude: number;
    bearing_deg: number | null;
}

/**
 * Reads live telemetry from Redux store.
 * WS connection is managed separately by useWsDispatch in the parent.
 */
export function useLiveTelemetry(locomotiveId: string | null) {
    const sensorsRecord = useAppSelector((state) => state.telemetry.sensors);
    const gps = useAppSelector((state) => state.telemetry.gps);
    const locomotiveType = useAppSelector((state) => state.telemetry.locomotiveType);
    const routeName = useAppSelector((state) => state.telemetry.routeName);
    const lastUpdated = useAppSelector((state) => state.telemetry.lastUpdated);

    // Build a Map for backward compat with existing components
    const sensors = useMemo(() => {
        const map = new Map<string, TelemetryReading>();
        for (const [sensorType, data] of Object.entries(sensorsRecord)) {
            map.set(sensorType, {
                locomotive_id: locomotiveId ?? '',
                locomotive_type: locomotiveType ?? '',
                sensor_type: sensorType as SensorType,
                value: data.current,
                filtered_value: null,
                unit: data.unit,
                timestamp: lastUpdated ? new Date(lastUpdated).toISOString() : '',
                latitude: gps?.latitude ?? null,
                longitude: gps?.longitude ?? null,
            });
        }
        return map;
    }, [sensorsRecord, gps, locomotiveId, locomotiveType, lastUpdated]);

    const position: Position | null = gps;

    return { sensors, position, routeName };
}
