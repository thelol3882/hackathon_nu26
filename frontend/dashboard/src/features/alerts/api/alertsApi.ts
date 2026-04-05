import { baseApi } from '@/shared/api/baseApi';
import type { AlertEvent, AlertsQuery } from '../types';

export const alertsApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getAlerts: builder.query<AlertEvent[], AlertsQuery>({
            query: (params) => ({
                url: '/alerts/',
                params,
            }),
            providesTags: (result) =>
                result
                    ? [
                          ...result.map(({ id }) => ({ type: 'Alert' as const, id })),
                          { type: 'Alert' as const, id: 'LIST' },
                      ]
                    : [{ type: 'Alert' as const, id: 'LIST' }],
        }),

        getAlert: builder.query<AlertEvent, string>({
            query: (id) => `/alerts/${id}`,
            providesTags: (_result, _error, id) => [{ type: 'Alert' as const, id }],
        }),

        acknowledgeAlert: builder.mutation<AlertEvent, string>({
            query: (id) => ({
                url: `/alerts/${id}/acknowledge`,
                method: 'POST',
            }),
            invalidatesTags: (_result, _error, id) => [
                { type: 'Alert' as const, id },
                { type: 'Alert' as const, id: 'LIST' },
            ],
        }),
    }),
});

export const { useGetAlertsQuery, useGetAlertQuery, useAcknowledgeAlertMutation } = alertsApi;
