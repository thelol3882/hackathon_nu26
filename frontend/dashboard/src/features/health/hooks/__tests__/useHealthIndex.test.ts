import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { baseApi } from '@/shared/api/baseApi';
import { authReducer } from '@/store/authSlice';
import { telemetryReducer } from '@/store/slices/telemetrySlice';
import { healthReducer, healthUpdated } from '@/store/slices/healthSlice';
import { alertsReducer } from '@/store/slices/alertsSlice';
import type { HealthIndex } from '../../types';

const { mockUseGetHealthQuery } = vi.hoisted(() => ({
    mockUseGetHealthQuery: vi.fn(),
}));

vi.mock('../../api/healthApi', () => ({
    healthApi: {
        useGetHealthQuery: mockUseGetHealthQuery,
    },
}));

import { useHealthIndex } from '../useHealthIndex';

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
            // eslint-disable-next-line react/no-children-prop -- React 19 types require children in props
            React.createElement(Provider, { store: s, children }),
    };
}

const fakeHealth: HealthIndex = {
    locomotive_id: 'loc-1',
    locomotive_type: 'TE33A',
    overall_score: 85,
    category: 'Норма',
    top_factors: [],
    damage_penalty: 0,
    calculated_at: '2026-04-04T00:00:00Z',
};

beforeEach(() => {
    vi.clearAllMocks();
    mockUseGetHealthQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: undefined,
    });
});

describe('useHealthIndex', () => {
    it('returns null health when no locomotiveId', () => {
        const { wrapper } = createWrapper();
        const { result } = renderHook(() => useHealthIndex(null), { wrapper });

        expect(result.current.health).toBeNull();
        expect(result.current.isLoading).toBe(false);
        expect(mockUseGetHealthQuery).toHaveBeenCalledWith('', { skip: true });
    });

    it('returns REST data when no live updates', () => {
        mockUseGetHealthQuery.mockReturnValue({
            data: fakeHealth,
            isLoading: false,
            error: undefined,
        });

        const { wrapper } = createWrapper();
        const { result } = renderHook(() => useHealthIndex('loc-1'), { wrapper });

        expect(result.current.health).toEqual(fakeHealth);
        expect(result.current.isLoading).toBe(false);
    });

    it('returns live data when Redux health state is updated', () => {
        mockUseGetHealthQuery.mockReturnValue({
            data: fakeHealth,
            isLoading: false,
            error: undefined,
        });

        const { store, wrapper } = createWrapper();
        const { result } = renderHook(() => useHealthIndex('loc-1'), { wrapper });

        act(() => {
            store.dispatch(
                healthUpdated({
                    overall_score: 72,
                    category: 'Внимание',
                    locomotive_type: 'TE33A',
                    top_factors: [],
                    damage_penalty: 5,
                    calculated_at: '2026-04-04T00:01:00Z',
                }),
            );
        });

        expect(result.current.health?.overall_score).toBe(72);
        expect(result.current.health?.category).toBe('Внимание');
    });

    it('isLoading reflects RTK Query loading state', () => {
        mockUseGetHealthQuery.mockReturnValue({
            data: undefined,
            isLoading: true,
            error: undefined,
        });

        const { wrapper } = createWrapper();
        const { result } = renderHook(() => useHealthIndex('loc-1'), { wrapper });

        expect(result.current.isLoading).toBe(true);
    });
});
