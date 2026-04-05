import {baseApi} from '@/shared/api/baseApi';
import type {HealthIndex} from '../types';

export const healthApi = baseApi.injectEndpoints({
    endpoints: (build) => ({
        getHealth: build.query<HealthIndex, string>({
            query: (locomotiveId) => `/locomotives/${locomotiveId}/health`,
            providesTags: (_result, _error, locomotiveId) => [{type: 'Health', id: locomotiveId}],
        }),
        getHealthAt: build.query<HealthIndex, { locomotiveId: string; at: string }>({
            query: ({locomotiveId, at}) => ({
                url: `/locomotives/${locomotiveId}/health/at`,
                params: {at},
            }),
        }),
    }),
});

export const {useGetHealthQuery, useGetHealthAtQuery} = healthApi;
