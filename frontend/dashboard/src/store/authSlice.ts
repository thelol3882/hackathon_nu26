import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

interface AuthState {
    accessToken: string | null;
    username: string | null;
    role: string | null;
}

const initialState: AuthState = {
    accessToken: null,
    username: null,
    role: null,
};

const authSlice = createSlice({
    name: 'auth',
    initialState,
    reducers: {
        setCredentials(
            state,
            action: PayloadAction<{ access_token: string; username: string; role: string }>,
        ) {
            state.accessToken = action.payload.access_token;
            state.username = action.payload.username;
            state.role = action.payload.role;
        },
        logout(state) {
            state.accessToken = null;
            state.username = null;
            state.role = null;
        },
    },
    selectors: {
        selectAccessToken: (state) => state.accessToken,
        selectUsername: (state) => state.username,
        selectRole: (state) => state.role,
        selectIsAuthenticated: (state) => !!state.accessToken,
        selectIsAdmin: (state) => state.role === 'admin',
    },
});

export const { setCredentials, logout } = authSlice.actions;
export const {
    selectAccessToken,
    selectUsername,
    selectRole,
    selectIsAuthenticated,
    selectIsAdmin,
} = authSlice.selectors;
export const authReducer = authSlice.reducer;
