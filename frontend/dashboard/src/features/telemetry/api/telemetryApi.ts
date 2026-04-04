import { baseApi } from '@/shared/api/baseApi';
import type {
    TelemetryBucket,
    TelemetryQuery,
    TelemetryRawQuery,
    TelemetryReading,
} from '../types';

export const telemetryApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getTelemetry: builder.query<TelemetryBucket[], TelemetryQuery>({
            query: (params) => ({
                url: '/telemetry/',
                params,
            }),
            providesTags: [{ type: 'Telemetry', id: 'LIST' }],
        }),
        getRawTelemetry: builder.query<TelemetryReading[], TelemetryRawQuery>({
            query: (params) => ({
                url: '/telemetry/raw',
                params,
            }),
        }),
    }),
});

export const { useGetTelemetryQuery, useGetRawTelemetryQuery } = telemetryApi;
