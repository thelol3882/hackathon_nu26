import { decode } from '@msgpack/msgpack';

type MessageHandler = (data: unknown) => void;

export type WireFormat = 'json' | 'msgpack';

export interface WsManagerOptions {
    url: string;
    wireFormat?: WireFormat;
    onStatusChange?: (status: WsStatus) => void;
    maxReconnectAttempts?: number;
}

export type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

export class WebSocketManager {
    private ws: WebSocket | null = null;
    private url: string;
    private handlers = new Set<MessageHandler>();
    private status: WsStatus = 'disconnected';
    private onStatusChange?: (status: WsStatus) => void;
    private reconnectAttempts = 0;
    private maxReconnectAttempts: number;
    private wireFormat: WireFormat;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private disposed = false;

    constructor(options: WsManagerOptions) {
        this.url = options.url;
        this.wireFormat = options.wireFormat ?? 'json';
        this.onStatusChange = options.onStatusChange;
        this.maxReconnectAttempts = options.maxReconnectAttempts ?? 10;
    }

    connect() {
        if (this.disposed) return;
        this.setStatus('connecting');

        this.ws = new WebSocket(this.url);
        if (this.wireFormat === 'msgpack') {
            this.ws.binaryType = 'arraybuffer';
        }

        this.ws.onopen = () => {
            this.reconnectAttempts = 0;
            this.setStatus('connected');
        };

        this.ws.onmessage = (event: MessageEvent) => {
            try {
                const data = this.decodeMessage(event.data);
                if (data && typeof data === 'object' && 'type' in data && (data as Record<string, unknown>).type === 'ping') return;
                this.handlers.forEach((handler) => handler(data));
            } catch {
                // ignore malformed messages
            }
        };

        this.ws.onclose = (event: CloseEvent) => {
            if (this.disposed) return;
            this.setStatus('disconnected');
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

    private decodeMessage(raw: unknown): unknown {
        if (raw instanceof ArrayBuffer) {
            return decode(new Uint8Array(raw));
        }
        if (typeof raw === 'string') {
            return JSON.parse(raw);
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
