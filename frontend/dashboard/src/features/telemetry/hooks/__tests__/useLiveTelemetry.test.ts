import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { baseApi } from '@/shared/api/baseApi';
import { authReducer } from '@/store/authSlice';
import { telemetryReducer, sensorUpdated, gpsUpdated } from '@/store/slices/telemetrySlice';
import { healthReducer } from '@/store/slices/healthSlice';
import { alertsReducer } from '@/store/slices/alertsSlice';
import { useLiveTelemetry } from '../useLiveTelemetry';

function createTestStore() {
  return configureStore({
    reducer: {
      [baseApi.reducerPath]: baseApi.reducer,
      auth: authReducer,
      telemetry: telemetryReducer,
      health: healthReducer,
      alerts: alertsReducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(baseApi.middleware),
  });
}

function createWrapper(store?: ReturnType<typeof createTestStore>) {
  const s = store ?? createTestStore();
  return {
    store: s,
    wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(Provider, { store: s }, children),
  };
}

describe('useLiveTelemetry', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('returns empty sensors map when no locomotiveId', () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useLiveTelemetry(null), { wrapper });

    expect(result.current.sensors.size).toBe(0);
    expect(result.current.position).toBeNull();
  });

  it('updates sensor map when Redux state changes', () => {
    const { store, wrapper } = createWrapper();
    const { result } = renderHook(() => useLiveTelemetry('loco-1'), { wrapper });

    act(() => {
      store.dispatch(
        sensorUpdated({
          sensorType: 'diesel_rpm',
          value: 800,
          unit: 'rpm',
          time: new Date('2026-04-04T12:00:00Z').getTime(),
          locomotiveType: 'TE33A',
        }),
      );
    });

    expect(result.current.sensors.size).toBe(1);
    const reading = result.current.sensors.get('diesel_rpm')!;
    expect(reading.value).toBe(800);
    expect(reading.locomotive_id).toBe('loco-1');
  });

  it('updates position when GPS dispatched to Redux', () => {
    const { store, wrapper } = createWrapper();
    const { result } = renderHook(() => useLiveTelemetry('loco-1'), { wrapper });

    act(() => {
      store.dispatch(gpsUpdated({ latitude: 51.1, longitude: 71.4 }));
    });

    expect(result.current.position).toEqual({ latitude: 51.1, longitude: 71.4 });
  });
});
