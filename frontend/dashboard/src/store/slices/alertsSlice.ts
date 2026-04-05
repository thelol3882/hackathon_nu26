import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { AlertSeverity } from '@/features/alerts/types';

const MAX_ALERTS = 100;

interface AlertItem {
    id: string;
    locomotive_id: string;
    sensor_type: string;
    severity: AlertSeverity;
    value: number;
    message: string;
    recommendation: string;
    timestamp: string;
    acknowledged: boolean;
}

interface AlertsState {
    items: AlertItem[];
    unacknowledgedCount: number;
}

const initialState: AlertsState = {
    items: [],
    unacknowledgedCount: 0,
};

function countUnacknowledged(items: AlertItem[]): number {
    let count = 0;
    for (const item of items) {
        if (!item.acknowledged) count++;
    }
    return count;
}

const alertsSlice = createSlice({
    name: 'alerts',
    initialState,
    reducers: {
        alertReceived(state, action: PayloadAction<AlertItem>) {
            state.items = [action.payload, ...state.items].slice(0, MAX_ALERTS);
            state.unacknowledgedCount = countUnacknowledged(state.items);
        },
        alertAcknowledged(state, action: PayloadAction<string>) {
            const alert = state.items.find((a) => a.id === action.payload);
            if (alert) {
                alert.acknowledged = true;
                state.unacknowledgedCount = countUnacknowledged(state.items);
            }
        },
        alertsReset() {
            return initialState;
        },
    },
});

export const { alertReceived, alertAcknowledged, alertsReset } = alertsSlice.actions;
export const alertsReducer = alertsSlice.reducer;
