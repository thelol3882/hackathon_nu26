import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLiveTelemetry } from '../useLiveTelemetry';

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

/** Build a wire-format telemetry envelope matching the backend shape. */
function makeWireTelemetry(
    sensors: { sensor_type: string; value: number; unit: string }[],
    gps: { latitude: number; longitude: number } | null = null,
) {
    return {
        locomotive_id: 'loco-1',
        locomotive_type: 'TE33A',
        timestamp: '2026-04-04T12:00:00Z',
        gps,
        sensors,
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

        const wire = makeWireTelemetry([{ sensor_type: 'diesel_rpm', value: 800, unit: 'rpm' }]);

        act(() => {
            capturedHandler!({ type: 'telemetry', data: wire });
        });

        expect(result.current.sensors.size).toBe(0);

        act(() => {
            vi.advanceTimersByTime(250);
        });

        expect(result.current.sensors.size).toBe(1);
        const reading = result.current.sensors.get('diesel_rpm')!;
        expect(reading.value).toBe(800);
        expect(reading.locomotive_id).toBe('loco-1');
    });

    it('updates position from readings with lat/lng', () => {
        let capturedHandler: SubscribeHandler | null = null;
        mockSubscribe.mockImplementation((handler) => {
            capturedHandler = handler;
            return () => {};
        });

        const { result } = renderHook(() => useLiveTelemetry('loco-1'));

        const wire = makeWireTelemetry([{ sensor_type: 'speed_actual', value: 60, unit: 'km/h' }], {
            latitude: 51.1,
            longitude: 71.4,
        });

        act(() => {
            capturedHandler!({ type: 'telemetry', data: wire });
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
