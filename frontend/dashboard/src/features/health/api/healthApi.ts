import { baseApi } from '@/shared/api/baseApi';
import type { HealthIndex } from '../types';

export const healthApi = baseApi.injectEndpoints({
    endpoints: (build) => ({
        getHealth: build.query<HealthIndex, string>({
            query: (locomotiveId) => `/locomotives/${locomotiveId}/health`,
            providesTags: (_result, _error, locomotiveId) => [{ type: 'Health', id: locomotiveId }],
        }),
    }),
});

export const { useGetHealthQuery } = healthApi;
