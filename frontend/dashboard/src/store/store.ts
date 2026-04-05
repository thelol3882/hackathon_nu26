import { configureStore } from '@reduxjs/toolkit';
import { setupListeners } from '@reduxjs/toolkit/query';
import { baseApi } from '@/shared/api/baseApi';
import { authReducer } from './authSlice';
import { telemetryReducer } from './slices/telemetrySlice';
import { healthReducer } from './slices/healthSlice';
import { alertsReducer } from './slices/alertsSlice';

export const store = configureStore({
    reducer: {
        [baseApi.reducerPath]: baseApi.reducer,
        auth: authReducer,
        telemetry: telemetryReducer,
        health: healthReducer,
        alerts: alertsReducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(baseApi.middleware),
});

setupListeners(store.dispatch);

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
