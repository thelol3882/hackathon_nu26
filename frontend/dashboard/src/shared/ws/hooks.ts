import { useEffect, useRef, useState, useCallback } from 'react';
import { store } from '@/store/store';
import { WebSocketManager, type WsStatus } from './manager';

function getWsBaseUrl(): string {
    if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
    if (typeof window === 'undefined') return 'ws://localhost:8010';
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}`;
}

function getApiBaseUrl(): string {
    if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
    if (typeof window === 'undefined') return 'http://localhost:8000';
    return `${window.location.origin}/api`;
}

const WS_BASE_URL = getWsBaseUrl();
const API_BASE_URL = getApiBaseUrl();

/**
 * Reads the current JWT access token from the Redux store.
 * Called lazily by the WebSocketManager on each connect/reconnect
 * so it always gets the freshest token.
 */
function getAccessToken(): string | null {
    return store.getState().auth.accessToken;
}

/** Shared managers keyed by path.  Ref-counted so the socket is
 *  closed only when the last consumer unmounts. */
const sharedManagers = new Map<string, { manager: WebSocketManager; refCount: number }>();

function acquireManager(path: string, onStatusChange: (s: WsStatus) => void): WebSocketManager {
    const existing = sharedManagers.get(path);
    if (existing) {
        existing.refCount++;
        return existing.manager;
    }
    const manager = new WebSocketManager({
        path,
        wsBaseUrl: WS_BASE_URL,
        apiBaseUrl: API_BASE_URL,
        getAccessToken,
        onStatusChange,
    });
    sharedManagers.set(path, { manager, refCount: 1 });
    manager.connect();
    return manager;
}

function releaseManager(path: string): void {
    const entry = sharedManagers.get(path);
    if (!entry) return;
    entry.refCount--;
    if (entry.refCount <= 0) {
        entry.manager.dispose();
        sharedManagers.delete(path);
    }
}

export function useWebSocket(path: string | null) {
    const [status, setStatus] = useState<WsStatus>('disconnected');
    const managerRef = useRef<WebSocketManager | null>(null);
    const pathRef = useRef<string | null>(null);

    useEffect(() => {
        if (!path) return;

        const manager = acquireManager(path, setStatus);
        managerRef.current = manager;
        pathRef.current = path;

        return () => {
            releaseManager(path);
            managerRef.current = null;
            pathRef.current = null;
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
