import '@testing-library/jest-dom/vitest';

class MockWebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;

    url: string;
    readyState = MockWebSocket.CONNECTING;
    onopen: ((ev: Event) => void) | null = null;
    onclose: ((ev: CloseEvent) => void) | null = null;
    onmessage: ((ev: MessageEvent) => void) | null = null;
    onerror: ((ev: Event) => void) | null = null;

    constructor(url: string) {
        this.url = url;
    }

    send() {
    }

    close() {
        this.readyState = MockWebSocket.CLOSED;
    }

    simulateOpen() {
        this.readyState = MockWebSocket.OPEN;
        this.onopen?.(new Event('open'));
    }

    simulateMessage(data: unknown) {
        this.onmessage?.(new MessageEvent('message', {data: JSON.stringify(data)}));
    }

    simulateClose(code = 1000, reason = '') {
        this.readyState = MockWebSocket.CLOSED;
        this.onclose?.({code, reason, wasClean: code === 1000} as CloseEvent);
    }

    simulateError() {
        this.onerror?.(new Event('error'));
    }
}

(globalThis as unknown as Record<string, unknown>).WebSocket = MockWebSocket;
(globalThis as unknown as Record<string, unknown>).MockWebSocket = MockWebSocket;
