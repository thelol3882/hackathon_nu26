import { baseApi } from '@/shared/api/baseApi';
import type { RouteInfo } from '../types';

// Route catalogue is static server-side, so cache forever.
export const routesApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getRoutes: builder.query<RouteInfo[], void>({
            query: () => ({ url: '/routes/' }),
            keepUnusedDataFor: Number.POSITIVE_INFINITY,
        }),
    }),
});

export const { useGetRoutesQuery } = routesApi;
