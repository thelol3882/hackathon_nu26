import {baseApi} from '@/shared/api/baseApi';
import type {
    TelemetryBucket,
    TelemetryQuery,
    TelemetryRawQuery,
    TelemetryReading,
    TelemetrySnapshotItem,
} from '../types';

export const telemetryApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getTelemetry: builder.query<TelemetryBucket[], TelemetryQuery>({
            query: (params) => ({
                url: '/telemetry/',
                params,
            }),
            providesTags: [{type: 'Telemetry', id: 'LIST'}],
        }),
        getRawTelemetry: builder.query<TelemetryReading[], TelemetryRawQuery>({
            query: (params) => ({
                url: '/telemetry/raw',
                params,
            }),
        }),
        getTelemetrySnapshot: builder.query<
            TelemetrySnapshotItem[],
            { locomotive_id: string; at: string }
        >({
            query: (params) => ({
                url: '/telemetry/snapshot',
                params,
            }),
        }),
    }),
});

export const {useGetTelemetryQuery, useGetRawTelemetryQuery, useGetTelemetrySnapshotQuery} =
    telemetryApi;
