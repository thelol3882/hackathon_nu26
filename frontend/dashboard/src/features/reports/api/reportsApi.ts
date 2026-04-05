import {baseApi} from '@/shared/api/baseApi';
import type {ReportRequest, ReportResponse, ReportsQuery} from '../types';

export const reportsApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        generateReport: builder.mutation<ReportResponse, ReportRequest>({
            query: (body) => ({
                url: '/reports/generate',
                method: 'POST',
                body,
            }),
            invalidatesTags: [{type: 'Report', id: 'LIST'}],
        }),
        getReports: builder.query<ReportResponse[], ReportsQuery>({
            query: (params) => ({
                url: '/reports/',
                params,
            }),
            providesTags: [{type: 'Report', id: 'LIST'}],
        }),
        getReport: builder.query<ReportResponse, string>({
            query: (id) => `/reports/${id}`,
            providesTags: (_result, _error, id) => [{type: 'Report', id}],
        }),
    }),
});

export const {useGenerateReportMutation, useGetReportsQuery, useGetReportQuery} = reportsApi;
