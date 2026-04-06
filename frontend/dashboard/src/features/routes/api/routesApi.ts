import { baseApi } from '@/shared/api/baseApi';
import type { RouteInfo } from '../types';

/**
 * Fetches the canonical railway route catalogue. The data is static
 * server-side (see `shared/route_geometry.py`), so we let RTK Query
 * cache it forever — `keepUnusedDataFor: Infinity` keeps the entry in
 * the store even after every consumer unmounts.
 */
export const routesApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getRoutes: builder.query<RouteInfo[], void>({
            query: () => ({ url: '/routes/' }),
            keepUnusedDataFor: Number.POSITIVE_INFINITY,
        }),
    }),
});

export const { useGetRoutesQuery } = routesApi;
