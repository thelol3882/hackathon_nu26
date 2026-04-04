import { useEffect, useRef, useState, useCallback } from 'react';
import { WebSocketManager, type WsStatus, type WireFormat } from './manager';

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
const WIRE_FORMAT: WireFormat = (process.env.NEXT_PUBLIC_WS_WIRE_FORMAT as WireFormat) || 'json';

export function useWebSocket(path: string | null) {
    const [status, setStatus] = useState<WsStatus>('disconnected');
    const managerRef = useRef<WebSocketManager | null>(null);

    useEffect(() => {
        if (!path) return;

        const manager = new WebSocketManager({
            url: `${WS_BASE_URL}${path}`,
            wireFormat: WIRE_FORMAT,
            onStatusChange: setStatus,
        });
        managerRef.current = manager;
        manager.connect();

        return () => {
            manager.dispose();
            managerRef.current = null;
        };
    }, [path]);

    const subscribe = useCallback(
        (handler: (data: unknown) => void) => {
            return managerRef.current?.subscribe(handler) ?? (() => {});
        },
        [],
    );

    return { status, subscribe };
}
