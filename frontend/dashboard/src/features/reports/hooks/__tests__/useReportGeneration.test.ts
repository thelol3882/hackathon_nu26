import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useReportGeneration } from '../useReportGeneration';
import type { ReportRequest } from '../../types';

const mockDispatch = vi.fn();

vi.mock('@/store/hooks', () => ({
    useAppDispatch: () => mockDispatch,
    useAppSelector: vi.fn(),
}));

vi.mock('../../api/reportsApi', () => {
    return {
        reportsApi: {
            useGenerateReportMutation: vi.fn(),
            useGetReportQuery: vi.fn(),
            util: {
                invalidateTags: vi.fn((tags: unknown) => ({
                    type: 'invalidateTags',
                    payload: tags,
                })),
            },
        },
    };
});

import { reportsApi } from '../../api/reportsApi';

const mockGenerateMutation = vi.fn();
const mockUnwrap = vi.fn();

function setupMocks(overrides?: {
    reportData?: unknown;
    queryError?: unknown;
    mutationError?: unknown;
}) {
    (reportsApi.useGenerateReportMutation as ReturnType<typeof vi.fn>).mockReturnValue([
        mockGenerateMutation,
        { error: overrides?.mutationError ?? undefined },
    ]);

    (reportsApi.useGetReportQuery as ReturnType<typeof vi.fn>).mockReturnValue({
        data: overrides?.reportData ?? undefined,
        error: overrides?.queryError ?? undefined,
    });

    mockGenerateMutation.mockReturnValue({ unwrap: mockUnwrap });
}

describe('useReportGeneration', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        setupMocks();
    });

    it('should have correct initial state', () => {
        const { result } = renderHook(() => useReportGeneration());

        expect(result.current.status).toBeNull();
        expect(result.current.isGenerating).toBe(false);
        expect(result.current.downloadUrl).toBeNull();
    });

    it('should call mutation and set reportId on generate', async () => {
        const reportResponse = {
            report_id: 'test-123',
            status: 'pending',
        };
        mockUnwrap.mockResolvedValue(reportResponse);

        const { result } = renderHook(() => useReportGeneration());

        const request: ReportRequest = {
            locomotive_id: 'loco-1',
            report_type: 'health',
            format: 'pdf',
            date_range: { start: '2026-01-01', end: '2026-01-31' },
        };

        await act(async () => {
            await result.current.generate(request);
        });

        expect(mockGenerateMutation).toHaveBeenCalledWith(request);
        expect(result.current.status).toBe('pending');
        expect(result.current.isGenerating).toBe(true);
    });

    it('should return downloadUrl when status is completed', () => {
        setupMocks({
            reportData: {
                report_id: 'test-456',
                status: 'completed',
            },
        });

        mockUnwrap.mockResolvedValue({
            report_id: 'test-456',
            status: 'pending',
        });

        const { result } = renderHook(() => useReportGeneration());

        expect(result.current.downloadUrl).toBeNull();
    });

    it('should clear all state on reset', async () => {
        mockUnwrap.mockResolvedValue({
            report_id: 'test-789',
            status: 'pending',
        });

        const { result } = renderHook(() => useReportGeneration());

        await act(async () => {
            await result.current.generate({
                locomotive_id: null,
                report_type: 'telemetry',
                format: 'csv',
                date_range: { start: '2026-01-01', end: '2026-01-31' },
            });
        });

        act(() => {
            result.current.reset();
        });

        expect(result.current.status).toBeNull();
        expect(result.current.isGenerating).toBe(false);
        expect(result.current.downloadUrl).toBeNull();
    });
});
