import { baseApi } from '@/shared/api/baseApi';
import type {
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
    UsersListResponse,
} from '../types';

export const authApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        login: builder.mutation<LoginResponse, LoginRequest>({
            query: (body) => ({
                url: '/auth/login',
                method: 'POST',
                body,
            }),
        }),
        register: builder.mutation<UserResponse, RegisterRequest>({
            query: (body) => ({
                url: '/auth/register',
                method: 'POST',
                body,
            }),
            invalidatesTags: [{ type: 'User', id: 'LIST' }],
        }),
        getUsers: builder.query<UsersListResponse, void>({
            query: () => '/auth/users',
            providesTags: [{ type: 'User', id: 'LIST' }],
        }),
    }),
});

export const { useLoginMutation, useRegisterMutation, useGetUsersQuery } = authApi;
