import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLiveTelemetry } from '../useLiveTelemetry';
import type { TelemetryReading } from '../../types';

type SubscribeHandler = (data: unknown) => void;

const mockSubscribe = vi.fn<(handler: SubscribeHandler) => () => void>();
const mockStatus = vi.fn(() => 'disconnected' as string);

vi.mock('@/shared/ws/hooks', () => ({
    useWebSocket: () => ({
        get status() {
            return mockStatus();
        },
        subscribe: mockSubscribe,
    }),
}));

function makeTelemetryReading(overrides: Partial<TelemetryReading> = {}): TelemetryReading {
    return {
        locomotive_id: 'loco-1',
        locomotive_type: 'TE33A',
        sensor_type: 'diesel_rpm',
        value: 750,
        filtered_value: null,
        unit: 'rpm',
        timestamp: '2026-04-04T12:00:00Z',
        latitude: null,
        longitude: null,
        ...overrides,
    };
}

describe('useLiveTelemetry', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        mockSubscribe.mockImplementation(() => () => {});
        mockStatus.mockReturnValue('disconnected');
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.clearAllMocks();
    });

    it('returns empty sensors map when no locomotiveId', () => {
        const { result } = renderHook(() => useLiveTelemetry(null));

        expect(result.current.sensors.size).toBe(0);
        expect(result.current.position).toBeNull();
    });

    it('updates sensor map when telemetry message arrives', () => {
        let capturedHandler: SubscribeHandler | null = null;
        mockSubscribe.mockImplementation((handler) => {
            capturedHandler = handler;
            return () => {};
        });

        const { result } = renderHook(() => useLiveTelemetry('loco-1'));

        const reading = makeTelemetryReading({ sensor_type: 'diesel_rpm', value: 800 });

        act(() => {
            capturedHandler!({ type: 'telemetry', data: reading });
        });

        // Before timer flush, state should still be empty
        expect(result.current.sensors.size).toBe(0);

        // Advance timer to trigger the 250ms batch flush
        act(() => {
            vi.advanceTimersByTime(250);
        });

        expect(result.current.sensors.size).toBe(1);
        expect(result.current.sensors.get('diesel_rpm')).toEqual(reading);
    });

    it('updates position from readings with lat/lng', () => {
        let capturedHandler: SubscribeHandler | null = null;
        mockSubscribe.mockImplementation((handler) => {
            capturedHandler = handler;
            return () => {};
        });

        const { result } = renderHook(() => useLiveTelemetry('loco-1'));

        const reading = makeTelemetryReading({
            sensor_type: 'speed_actual',
            latitude: 51.1,
            longitude: 71.4,
        });

        act(() => {
            capturedHandler!({ type: 'telemetry', data: reading });
        });

        act(() => {
            vi.advanceTimersByTime(250);
        });

        expect(result.current.position).toEqual({ latitude: 51.1, longitude: 71.4 });
    });

    it('connectionStatus reflects WS status', () => {
        mockStatus.mockReturnValue('connected');

        const { result } = renderHook(() => useLiveTelemetry('loco-1'));

        expect(result.current.connectionStatus).toBe('connected');
    });
});
