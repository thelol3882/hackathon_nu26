import { useEffect, useRef, useState } from 'react';
import { useWebSocket } from '@/shared/ws/hooks';
import type { TelemetryReading } from '../types';

interface Position {
    latitude: number;
    longitude: number;
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
            const message = data as { type?: string; data?: TelemetryReading };
            if (message.type !== 'telemetry' || !message.data) return;

            const reading = message.data;
            pendingUpdatesRef.current.push(reading);

            if (reading.latitude != null && reading.longitude != null) {
                pendingPositionRef.current = {
                    latitude: reading.latitude,
                    longitude: reading.longitude,
                };
            }
        });

        return unsubscribe;
    }, [subscribe]);

    return { sensors, position, connectionStatus: status };
}
