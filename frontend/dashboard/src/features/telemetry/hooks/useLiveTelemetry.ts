import { useEffect, useRef, useState } from 'react';
import { useWebSocket } from '@/shared/ws/hooks';
import type { SensorType, TelemetryReading } from '../types';

interface Position {
    latitude: number;
    longitude: number;
}

/** Shape of the telemetry envelope coming over the wire. */
interface WireTelemetry {
    locomotive_id: string;
    locomotive_type: string;
    timestamp: string;
    gps: { latitude: number; longitude: number } | null;
    sensors: { sensor_type: string; value: number; unit: string }[];
}

export function useLiveTelemetry(locomotiveId: string | null) {
    const path = locomotiveId ? `/ws/live/${locomotiveId}` : null;
    const { status, subscribe } = useWebSocket(path);

    const sensorMapRef = useRef<Map<string, TelemetryReading>>(new Map());
    const pendingUpdatesRef = useRef<TelemetryReading[]>([]);
    const pendingPositionRef = useRef<Position | null>(null);

    const [sensors, setSensors] = useState<Map<string, TelemetryReading>>(new Map());
    const [position, setPosition] = useState<Position | null>(null);

    // Flush batched updates every 250ms
    useEffect(() => {
        const interval = setInterval(() => {
            if (pendingUpdatesRef.current.length > 0) {
                for (const reading of pendingUpdatesRef.current) {
                    sensorMapRef.current.set(reading.sensor_type, reading);
                }
                pendingUpdatesRef.current = [];
                setSensors(new Map(sensorMapRef.current));
            }
            if (pendingPositionRef.current !== null) {
                setPosition(pendingPositionRef.current);
                pendingPositionRef.current = null;
            }
        }, 250);

        return () => clearInterval(interval);
    }, []);

    // Subscribe to WebSocket messages
    useEffect(() => {
        const unsubscribe = subscribe((data: unknown) => {
            const message = data as { type?: string; data?: WireTelemetry };
            if (message.type !== 'telemetry' || !message.data) return;

            const { locomotive_id, locomotive_type, timestamp, gps, sensors } = message.data;

            for (const s of sensors) {
                pendingUpdatesRef.current.push({
                    locomotive_id,
                    locomotive_type,
                    sensor_type: s.sensor_type as SensorType,
                    value: s.value,
                    filtered_value: null,
                    unit: s.unit,
                    timestamp,
                    latitude: gps?.latitude ?? null,
                    longitude: gps?.longitude ?? null,
                });
            }

            if (gps) {
                pendingPositionRef.current = { latitude: gps.latitude, longitude: gps.longitude };
            }
        });

        return unsubscribe;
    }, [subscribe]);

    return { sensors, position, connectionStatus: status };
}
