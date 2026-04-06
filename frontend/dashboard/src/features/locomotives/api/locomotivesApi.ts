import { baseApi } from '@/shared/api/baseApi';
import type {
    Locomotive,
    LocomotiveCreate,
    LocomotiveListResponse,
    LocomotiveQueryParams,
} from '../types';

export const locomotivesApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getLocomotives: builder.query<LocomotiveListResponse, LocomotiveQueryParams>({
            query: ({ offset, limit, search, model } = {}) => ({
                url: '/locomotives/',
                params: { offset, limit, search, model },
            }),
            serializeQueryArgs({ queryArgs }) {
                // Exclude offset so paginated results merge into one cache entry.
                const { search, model } = queryArgs ?? {};
                return { search, model };
            },
            merge(currentCache, newItems, { arg }) {
                const offset = arg?.offset ?? 0;
                if (offset === 0) {
                    return newItems;
                }
                return {
                    items: [...currentCache.items, ...newItems.items],
                    total: newItems.total,
                };
            },
            forceRefetch({ currentArg, previousArg }) {
                return (
                    currentArg?.offset !== previousArg?.offset ||
                    currentArg?.search !== previousArg?.search ||
                    currentArg?.model !== previousArg?.model
                );
            },
            providesTags: [{ type: 'Locomotive', id: 'LIST' }],
        }),
        getLocomotive: builder.query<Locomotive, string>({
            query: (id) => `/locomotives/${id}`,
            providesTags: (_result, _error, id) => [{ type: 'Locomotive', id }],
        }),
        createLocomotive: builder.mutation<Locomotive, LocomotiveCreate>({
            query: (body) => ({
                url: '/locomotives/',
                method: 'POST',
                body,
            }),
            invalidatesTags: [{ type: 'Locomotive', id: 'LIST' }],
        }),
    }),
});

export const { useGetLocomotivesQuery, useGetLocomotiveQuery, useCreateLocomotiveMutation } =
    locomotivesApi;
