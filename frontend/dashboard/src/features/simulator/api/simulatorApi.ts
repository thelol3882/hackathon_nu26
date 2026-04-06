import { baseApi } from '@/shared/api/baseApi';
import type {
    CreateSimulatedLocomotiveBody,
    SimulatedLocomotive,
    UpdateSimulatedLocomotiveBody,
} from '../types';

// Kept separate from locomotivesApi: the catalogue and the simulator are distinct concerns.
// Creation flow: catalogue first (to get a UUID), then simulator with that UUID.
export const simulatorApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        getSimulatedLocomotives: builder.query<SimulatedLocomotive[], void>({
            query: () => ({ url: '/simulator/locomotives' }),
            providesTags: (result) => [
                { type: 'SimulatorLoco' as const, id: 'LIST' },
                ...(result ?? []).map((l) => ({ type: 'SimulatorLoco' as const, id: l.id })),
            ],
        }),
        getSimulatedLocomotive: builder.query<SimulatedLocomotive, string>({
            query: (id) => ({ url: `/simulator/locomotives/${id}` }),
            providesTags: (_r, _e, id) => [{ type: 'SimulatorLoco', id }],
        }),
        createSimulatedLocomotive: builder.mutation<
            SimulatedLocomotive,
            CreateSimulatedLocomotiveBody
        >({
            query: (body) => ({
                url: '/simulator/locomotives',
                method: 'POST',
                body,
            }),
            invalidatesTags: [{ type: 'SimulatorLoco', id: 'LIST' }],
        }),
        updateSimulatedLocomotive: builder.mutation<
            SimulatedLocomotive,
            { id: string; body: UpdateSimulatedLocomotiveBody }
        >({
            query: ({ id, body }) => ({
                url: `/simulator/locomotives/${id}`,
                method: 'PATCH',
                body,
            }),
            invalidatesTags: (_r, _e, { id }) => [
                { type: 'SimulatorLoco', id },
                { type: 'SimulatorLoco', id: 'LIST' },
            ],
        }),
        deleteSimulatedLocomotive: builder.mutation<void, string>({
            query: (id) => ({
                url: `/simulator/locomotives/${id}`,
                method: 'DELETE',
            }),
            invalidatesTags: [{ type: 'SimulatorLoco', id: 'LIST' }],
        }),
    }),
});

export const {
    useGetSimulatedLocomotivesQuery,
    useGetSimulatedLocomotiveQuery,
    useCreateSimulatedLocomotiveMutation,
    useUpdateSimulatedLocomotiveMutation,
    useDeleteSimulatedLocomotiveMutation,
} = simulatorApi;
