import {useState, useCallback, useMemo} from 'react';
import {useAppDispatch} from '@/store/hooks';
import {reportsApi} from '../api/reportsApi';
import type {ReportRequest, ReportStatus} from '../types';

const TERMINAL_STATUSES: ReportStatus[] = ['completed', 'failed'];

export function useReportGeneration() {
    const dispatch = useAppDispatch();
    const [reportId, setReportId] = useState<string | null>(null);
    const [status, setStatus] = useState<ReportStatus | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);

    const [generateMutation, {error: mutationError}] = reportsApi.useGenerateReportMutation();

    const shouldPoll = reportId !== null && status !== null && !TERMINAL_STATUSES.includes(status);

    const {data: reportData, error: queryError} = reportsApi.useGetReportQuery(reportId!, {
        skip: !reportId,
        pollingInterval: shouldPoll ? 2000 : 0,
    });

    if (reportData && reportData.status !== status) {
        setStatus(reportData.status);
        if (TERMINAL_STATUSES.includes(reportData.status)) {
            setIsGenerating(false);
            dispatch(reportsApi.util.invalidateTags([{type: 'Report', id: 'LIST'}]));
        }
    }

    const generate = useCallback(
        async (request: ReportRequest) => {
            setIsGenerating(true);
            setStatus(null);
            try {
                const result = await generateMutation(request).unwrap();
                setReportId(result.report_id);
                setStatus(result.status);
            } catch {
                setIsGenerating(false);
            }
        },
        [generateMutation],
    );

    const downloadUrl = useMemo(() => {
        if (status === 'completed' && reportId) {
            return `/api/reports/${reportId}/download`;
        }
        return null;
    }, [status, reportId]);

    const reset = useCallback(() => {
        setReportId(null);
        setStatus(null);
        setIsGenerating(false);
    }, []);

    const error = mutationError || queryError || null;

    return {generate, status, isGenerating, downloadUrl, reset, error};
}
