import { baseApi } from '@/shared/api/baseApi';
import type {
    CreateSimulatedLocomotiveBody,
    SimulatedLocomotive,
    UpdateSimulatedLocomotiveBody,
} from '../types';

/**
 * RTK Query endpoints for the operator-driven simulator.
 *
 * `simulatorApi` is intentionally a separate slice from `locomotivesApi`
 * because the catalogue (which physical locos exist) and the simulator
 * (which of them are currently being simulated, with what parameters)
 * are two different concerns. The dashboard creates locos in both —
 * catalogue first to get a UUID, then simulator with that UUID.
 */
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
