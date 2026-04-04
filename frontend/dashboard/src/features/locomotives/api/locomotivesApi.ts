import { baseApi } from '@/shared/api/baseApi';
import type { Locomotive, LocomotiveCreate } from '../types';

export const locomotivesApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getLocomotives: builder.query<Locomotive[], { offset?: number; limit?: number }>({
            query: ({ offset, limit } = {}) => ({
                url: '/locomotives/',
                params: { offset, limit },
            }),
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
