import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLiveAlerts } from '../useLiveAlerts';
import type { AlertEvent } from '../../types';

type MessageHandler = (message: unknown) => void;

let capturedHandler: MessageHandler | null = null;
const mockSubscribe = vi.fn((handler: MessageHandler) => {
    capturedHandler = handler;
    return vi.fn(); // unsubscribe
});
const mockStatus = 'connected';

vi.mock('@/shared/ws/hooks', () => ({
    useWebSocket: vi.fn(() => ({
        status: mockStatus,
        subscribe: mockSubscribe,
    })),
}));

function makeAlertData(overrides: Partial<AlertEvent> = {}): AlertEvent {
    return {
        id: overrides.id ?? crypto.randomUUID(),
        locomotive_id: 'loco-1',
        sensor_type: 'temperature',
        severity: 'warning',
        value: 80,
        threshold_min: null,
        threshold_max: 75,
        message: 'Temperature exceeded',
        timestamp: new Date().toISOString(),
        acknowledged: false,
        ...overrides,
    };
}

function makeAlertEnvelope(overrides: Partial<AlertEvent> = {}) {
    return { type: 'alert', data: makeAlertData(overrides) };
}

describe('useLiveAlerts', () => {
    beforeEach(() => {
        capturedHandler = null;
        mockSubscribe.mockClear();
    });

    it('returns empty alerts when no locomotiveId', () => {
        const { result } = renderHook(() => useLiveAlerts(null));
        expect(result.current.alerts).toEqual([]);
    });

    it('adds alert when alert message arrives via subscribe callback', () => {
        const { result } = renderHook(() => useLiveAlerts('loco-1'));

        act(() => {
            capturedHandler!(makeAlertEnvelope({ id: 'a1' }));
        });

        expect(result.current.alerts).toHaveLength(1);
        expect(result.current.alerts[0].id).toBe('a1');
    });

    it('alerts are prepended (newest first)', () => {
        const { result } = renderHook(() => useLiveAlerts('loco-1'));

        act(() => {
            capturedHandler!(makeAlertEnvelope({ id: 'first' }));
        });
        act(() => {
            capturedHandler!(makeAlertEnvelope({ id: 'second' }));
        });

        expect(result.current.alerts[0].id).toBe('second');
        expect(result.current.alerts[1].id).toBe('first');
    });

    it('caps at 50 alerts', () => {
        const { result } = renderHook(() => useLiveAlerts('loco-1'));

        act(() => {
            for (let i = 0; i < 55; i++) {
                capturedHandler!(makeAlertEnvelope({ id: `alert-${i}` }));
            }
        });

        expect(result.current.alerts).toHaveLength(50);
        expect(result.current.alerts[0].id).toBe('alert-54');
    });

    it('clearAlerts empties the array', () => {
        const { result } = renderHook(() => useLiveAlerts('loco-1'));

        act(() => {
            capturedHandler!(makeAlertEnvelope({ id: 'a1' }));
            capturedHandler!(makeAlertEnvelope({ id: 'a2' }));
        });

        expect(result.current.alerts).toHaveLength(2);

        act(() => {
            result.current.clearAlerts();
        });

        expect(result.current.alerts).toEqual([]);
    });
});
