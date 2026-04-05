import {createSlice, type PayloadAction} from '@reduxjs/toolkit';

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

function loadFromStorage(): AuthState {
    if (typeof window === 'undefined') return emptyState;
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {
            const saved = JSON.parse(raw) as AuthState;
            if (saved.accessToken) {
                // Discard token if JWT has expired
                try {
                    const payload = JSON.parse(atob(saved.accessToken.split('.')[1]));
                    if (payload.exp && payload.exp * 1000 < Date.now()) {
                        localStorage.removeItem(STORAGE_KEY);
                        return emptyState;
                    }
                } catch {
                }
                return saved;
            }
        }
    } catch {
    }
    return emptyState;
}

function saveToStorage(state: AuthState) {
    if (typeof window === 'undefined') return;
    if (state.accessToken) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } else {
        localStorage.removeItem(STORAGE_KEY);
    }
}

function decodeRole(token: string): string {
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload.role ?? 'operator';
    } catch {
        return 'operator';
    }
}

const authSlice = createSlice({
    name: 'auth',
    initialState: loadFromStorage(),
    reducers: {
        hydrateAuth(state) {
            if (typeof window === 'undefined') return;
            const saved = loadFromStorage();
            state.accessToken = saved.accessToken;
            state.username = saved.username;
            state.role = saved.role;
        },
        setCredentials(
            state,
            action: PayloadAction<{ access_token: string; username: string; role?: string }>,
        ) {
            state.accessToken = action.payload.access_token;
            state.username = action.payload.username;
            state.role = action.payload.role ?? decodeRole(action.payload.access_token);
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

export const {hydrateAuth, setCredentials, logout} = authSlice.actions;
export const {
    selectAccessToken,
    selectUsername,
    selectRole,
    selectIsAuthenticated,
    selectIsAdmin,
} = authSlice.selectors;
export const authReducer = authSlice.reducer;
