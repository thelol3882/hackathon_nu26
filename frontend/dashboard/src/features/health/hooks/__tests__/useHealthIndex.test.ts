import {describe, it, expect, vi, beforeEach} from 'vitest';
import {renderHook, act} from '@testing-library/react';
import type {HealthIndex} from '../../types';

const {mockSubscribe, mockUnsubscribe, mockUseGetHealthQuery} = vi.hoisted(() => ({
    mockSubscribe: vi.fn(),
    mockUnsubscribe: vi.fn(),
    mockUseGetHealthQuery: vi.fn(),
}));

vi.mock('@/shared/ws/hooks', () => ({
    useWebSocket: vi.fn(() => ({
        status: 'connected' as const,
        subscribe: mockSubscribe.mockReturnValue(mockUnsubscribe),
    })),
}));

vi.mock('../../api/healthApi', () => ({
    healthApi: {
        useGetHealthQuery: mockUseGetHealthQuery,
    },
}));

import {useHealthIndex} from '../useHealthIndex';
import {useWebSocket} from '@/shared/ws/hooks';

const fakeHealth: HealthIndex = {
    locomotive_id: 'loc-1',
    locomotive_type: 'ТЭ33А',
    overall_score: 85,
    category: 'Норма',
    top_factors: [],
    damage_penalty: 0,
    calculated_at: '2026-04-04T00:00:00Z',
};

const fakeLiveHealth: HealthIndex = {
    locomotive_id: 'loc-1',
    locomotive_type: 'ТЭ33А',
    overall_score: 72,
    category: 'Внимание',
    top_factors: [],
    damage_penalty: 5,
    calculated_at: '2026-04-04T00:01:00Z',
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
        const {result} = renderHook(() => useHealthIndex(null));

        expect(result.current.health).toBeNull();
        expect(result.current.isLoading).toBe(false);
        expect(mockUseGetHealthQuery).toHaveBeenCalledWith('', {skip: true});
        expect(useWebSocket).toHaveBeenCalledWith(null);
    });

    it('returns REST data when no live updates', () => {
        mockUseGetHealthQuery.mockReturnValue({
            data: fakeHealth,
            isLoading: false,
            error: undefined,
        });

        const {result} = renderHook(() => useHealthIndex('loc-1'));

        expect(result.current.health).toEqual(fakeHealth);
        expect(result.current.isLoading).toBe(false);
    });

    it('returns live data when WS health message arrives', () => {
        mockUseGetHealthQuery.mockReturnValue({
            data: fakeHealth,
            isLoading: false,
            error: undefined,
        });

        const {result} = renderHook(() => useHealthIndex('loc-1'));

        const handler = mockSubscribe.mock.calls[0][0];
        expect(handler).toBeDefined();

        act(() => {
            handler({type: 'health', data: fakeLiveHealth});
        });

        expect(result.current.health).toEqual(fakeLiveHealth);
    });

    it('isLoading reflects RTK Query loading state', () => {
        mockUseGetHealthQuery.mockReturnValue({
            data: undefined,
            isLoading: true,
            error: undefined,
        });

        const {result} = renderHook(() => useHealthIndex('loc-1'));

        expect(result.current.isLoading).toBe(true);
    });
});
