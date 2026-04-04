import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

const STORAGE_KEY = 'ktz_auth';

interface AuthState {
    accessToken: string | null;
    username: string | null;
    role: string | null;
}

const emptyState: AuthState = {
    accessToken: null,
    username: null,
    role: null,
};

function saveToStorage(state: AuthState) {
    if (typeof window === 'undefined') return;
    if (state.accessToken) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } else {
        localStorage.removeItem(STORAGE_KEY);
    }
}

const authSlice = createSlice({
    name: 'auth',
    initialState: emptyState,
    reducers: {
        hydrateAuth(state) {
            if (typeof window === 'undefined') return;
            try {
                const raw = localStorage.getItem(STORAGE_KEY);
                if (raw) {
                    const saved = JSON.parse(raw) as AuthState;
                    state.accessToken = saved.accessToken;
                    state.username = saved.username;
                    state.role = saved.role;
                }
            } catch {
                // corrupted storage
            }
        },
        setCredentials(
            state,
            action: PayloadAction<{ access_token: string; username: string; role: string }>,
        ) {
            state.accessToken = action.payload.access_token;
            state.username = action.payload.username;
            state.role = action.payload.role;
            saveToStorage(state);
        },
        logout(state) {
            state.accessToken = null;
            state.username = null;
            state.role = null;
            saveToStorage(state);
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

export const { hydrateAuth, setCredentials, logout } = authSlice.actions;
export const {
    selectAccessToken,
    selectUsername,
    selectRole,
    selectIsAuthenticated,
    selectIsAdmin,
} = authSlice.selectors;
export const authReducer = authSlice.reducer;
