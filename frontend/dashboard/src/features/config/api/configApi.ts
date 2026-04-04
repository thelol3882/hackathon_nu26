import { baseApi } from '@/shared/api/baseApi';
import type { ThresholdConfig, WeightConfig } from '../types';

export const configApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getThresholds: builder.query<ThresholdConfig[], void>({
            query: () => '/config/thresholds',
            providesTags: [{ type: 'Threshold', id: 'LIST' }],
        }),
        updateThreshold: builder.mutation<
            ThresholdConfig,
            { sensor_type: string; min_value: number; max_value: number }
        >({
            query: ({ sensor_type, ...body }) => ({
                url: `/config/thresholds/${sensor_type}`,
                method: 'PUT',
                body,
            }),
            invalidatesTags: [{ type: 'Threshold', id: 'LIST' }],
        }),
        getWeights: builder.query<WeightConfig[], void>({
            query: () => '/config/weights',
            providesTags: [{ type: 'Weight', id: 'LIST' }],
        }),
        updateWeight: builder.mutation<WeightConfig, { sensor_type: string; weight: number }>({
            query: ({ sensor_type, ...body }) => ({
                url: `/config/weights/${sensor_type}`,
                method: 'PUT',
                body,
            }),
            invalidatesTags: [{ type: 'Weight', id: 'LIST' }],
        }),
    }),
});

export const {
    useGetThresholdsQuery,
    useUpdateThresholdMutation,
    useGetWeightsQuery,
    useUpdateWeightMutation,
} = configApi;
