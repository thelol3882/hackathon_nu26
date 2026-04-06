import { decode } from '@msgpack/msgpack';
import { encode } from '@msgpack/msgpack';

type MessageHandler = (data: unknown) => void;

export interface WsManagerOptions {
    /** WS path, e.g. /ws/live/LOCO-001 */
    path: string;
    /** WS base URL, e.g. ws://localhost or wss://example.com */
    wsBaseUrl: string;
    /** Single-use WS ticket fetcher; called on every (re)connect. Returns null on auth failure. */
    fetchTicket: () => Promise<string | null>;
    onStatusChange?: (status: WsStatus) => void;
    maxReconnectAttempts?: number;
}

export type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

export class WebSocketManager {
    private ws: WebSocket | null = null;
    private path: string;
    private wsBaseUrl: string;
    private fetchTicket: () => Promise<string | null>;
    private handlers = new Set<MessageHandler>();
    private status: WsStatus = 'disconnected';
    private onStatusChange?: (status: WsStatus) => void;
    private reconnectAttempts = 0;
    private maxReconnectAttempts: number;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private disposed = false;

    constructor(options: WsManagerOptions) {
        this.path = options.path;
        this.wsBaseUrl = options.wsBaseUrl;
        this.fetchTicket = options.fetchTicket;
        this.onStatusChange = options.onStatusChange;
        this.maxReconnectAttempts = options.maxReconnectAttempts ?? 10;
    }

    async connect() {
        if (this.disposed) return;
        this.setStatus('connecting');

        // Tickets are single-use (GETDEL in Redis), so fetch a fresh one per connect.
        const ticket = await this.fetchTicket();
        if (!ticket) {
            this.setStatus('disconnected');
            return;
        }

        const url = `${this.wsBaseUrl}${this.path}?ticket=${ticket}`;
        this.ws = new WebSocket(url);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
            this.reconnectAttempts = 0;
            this.setStatus('connected');
        };

        this.ws.onmessage = (event: MessageEvent) => {
            try {
                const data = this.decodeMessage(event.data);
                if (
                    data &&
                    typeof data === 'object' &&
                    'type' in data &&
                    (data as Record<string, unknown>).type === 'ping'
                ) {
                    this.sendPong();
                    return;
                }
                this.handlers.forEach((handler) => handler(data));
            } catch {
                // Drop malformed messages silently.
            }
        };

        this.ws.onclose = (event: CloseEvent) => {
            if (this.disposed) return;
            this.setStatus('disconnected');
            // Codes 4400/4401 mean the ticket or JWT is bad — no point retrying.
            if (event.code === 4401 || event.code === 4400) return;
            if (!event.wasClean) {
                this.scheduleReconnect();
            }
        };

        this.ws.onerror = () => {
            this.ws?.close();
        };
    }

    subscribe(handler: MessageHandler): () => void {
        this.handlers.add(handler);
        return () => {
            this.handlers.delete(handler);
        };
    }

    getStatus(): WsStatus {
        return this.status;
    }

    dispose() {
        this.disposed = true;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        this.ws?.close();
        this.ws = null;
        this.handlers.clear();
        this.setStatus('disconnected');
    }

    private sendPong() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        try {
            this.ws.send(encode({ type: 'pong' }));
        } catch {}
    }

    private decodeMessage(raw: unknown): unknown {
        if (raw instanceof ArrayBuffer) {
            return decode(new Uint8Array(raw));
        }
        return raw;
    }

    private setStatus(status: WsStatus) {
        this.status = status;
        this.onStatusChange?.(status);
    }

    private scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
        this.setStatus('reconnecting');
        const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000);
        this.reconnectAttempts++;
        this.reconnectTimer = setTimeout(() => {
            this.connect();
        }, delay);
    }
}
