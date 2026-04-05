import { useEffect, useRef, useState, useCallback } from 'react';
import { WebSocketManager, type WsStatus } from './manager';

function getWsBaseUrl(): string {
    if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
    if (typeof window === 'undefined') return 'ws://localhost:8000';
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}`;
}

const WS_BASE_URL = getWsBaseUrl();

/** Shared managers keyed by full URL.  Ref-counted so the socket is
 *  closed only when the last consumer unmounts. */
const sharedManagers = new Map<string, { manager: WebSocketManager; refCount: number }>();

function acquireManager(url: string, onStatusChange: (s: WsStatus) => void): WebSocketManager {
    const existing = sharedManagers.get(url);
    if (existing) {
        existing.refCount++;
        return existing.manager;
    }
    const manager = new WebSocketManager({ url, onStatusChange });
    sharedManagers.set(url, { manager, refCount: 1 });
    manager.connect();
    return manager;
}

function releaseManager(url: string): void {
    const entry = sharedManagers.get(url);
    if (!entry) return;
    entry.refCount--;
    if (entry.refCount <= 0) {
        entry.manager.dispose();
        sharedManagers.delete(url);
    }
}

export function useWebSocket(path: string | null) {
    const [status, setStatus] = useState<WsStatus>('disconnected');
    const managerRef = useRef<WebSocketManager | null>(null);
    const urlRef = useRef<string | null>(null);

    useEffect(() => {
        if (!path) return;

        const url = `${WS_BASE_URL}${path}`;
        const manager = acquireManager(url, setStatus);
        managerRef.current = manager;
        urlRef.current = url;

        return () => {
            releaseManager(url);
            managerRef.current = null;
            urlRef.current = null;
        };
    }, [path]);

    const subscribe = useCallback(
        (handler: (data: unknown) => void) => {
            return managerRef.current?.subscribe(handler) ?? (() => {});
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps -- Re-create when status/path changes so consumers re-subscribe after manager acquisition
        [status, path],
    );

    return { status, subscribe };
}
