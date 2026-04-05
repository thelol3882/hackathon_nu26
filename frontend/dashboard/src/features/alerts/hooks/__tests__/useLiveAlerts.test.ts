import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { baseApi } from '@/shared/api/baseApi';
import { authReducer } from '@/store/authSlice';
import { telemetryReducer } from '@/store/slices/telemetrySlice';
import { healthReducer } from '@/store/slices/healthSlice';
import { alertsReducer, alertReceived } from '@/store/slices/alertsSlice';
import { useLiveAlerts } from '../useLiveAlerts';
import type { AlertEvent } from '../../types';

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
    recommendation: '',
    timestamp: new Date().toISOString(),
    acknowledged: false,
    ...overrides,
  };
}

describe('useLiveAlerts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns empty alerts when no locomotiveId', () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useLiveAlerts(null), { wrapper });
    expect(result.current.alerts).toEqual([]);
  });

  it('adds alert when dispatched to Redux', () => {
    const { store, wrapper } = createWrapper();
    const { result } = renderHook(() => useLiveAlerts('loco-1'), { wrapper });

    act(() => {
      store.dispatch(alertReceived(makeAlertData({ id: 'a1' })));
    });

    expect(result.current.alerts).toHaveLength(1);
    expect(result.current.alerts[0].id).toBe('a1');
  });

  it('alerts are prepended (newest first)', () => {
    const { store, wrapper } = createWrapper();
    const { result } = renderHook(() => useLiveAlerts('loco-1'), { wrapper });

    act(() => {
      store.dispatch(alertReceived(makeAlertData({ id: 'first' })));
    });
    act(() => {
      store.dispatch(alertReceived(makeAlertData({ id: 'second' })));
    });

    expect(result.current.alerts[0].id).toBe('second');
    expect(result.current.alerts[1].id).toBe('first');
  });

  it('caps at 100 alerts', () => {
    const { store, wrapper } = createWrapper();
    const { result } = renderHook(() => useLiveAlerts('loco-1'), { wrapper });

    act(() => {
      for (let i = 0; i < 105; i++) {
        store.dispatch(alertReceived(makeAlertData({ id: `alert-${i}` })));
      }
    });

    expect(result.current.alerts).toHaveLength(100);
    expect(result.current.alerts[0].id).toBe('alert-104');
  });

  it('clearAlerts empties the array', () => {
    const { store, wrapper } = createWrapper();
    const { result } = renderHook(() => useLiveAlerts('loco-1'), { wrapper });

    act(() => {
      store.dispatch(alertReceived(makeAlertData({ id: 'a1' })));
      store.dispatch(alertReceived(makeAlertData({ id: 'a2' })));
    });

    expect(result.current.alerts).toHaveLength(2);

    act(() => {
      result.current.clearAlerts();
    });

    expect(result.current.alerts).toEqual([]);
  });
});
