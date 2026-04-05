import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

const MAX_HISTORY = 300;

interface SensorData {
    current: number;
    unit: string;
    history: Array<{ time: number; value: number }>;
}

interface TelemetryState {
    sensors: Record<string, SensorData>;
    gps: { latitude: number; longitude: number } | null;
    locomotiveType: string | null;
    lastUpdated: number | null;
}

const initialState: TelemetryState = {
    sensors: {},
    gps: null,
    locomotiveType: null,
    lastUpdated: null,
};

const telemetrySlice = createSlice({
    name: 'telemetry',
    initialState,
    reducers: {
        sensorUpdated(
            state,
            action: PayloadAction<{
                sensorType: string;
                value: number;
                unit: string;
                time: number;
                locomotiveType?: string;
            }>,
        ) {
            const { sensorType, value, unit, time, locomotiveType } = action.payload;
            const existing = state.sensors[sensorType];
            if (existing) {
                existing.current = value;
                existing.unit = unit;
                existing.history.push({ time, value });
                if (existing.history.length > MAX_HISTORY) {
                    existing.history = existing.history.slice(-MAX_HISTORY);
                }
            } else {
                state.sensors[sensorType] = {
                    current: value,
                    unit,
                    history: [{ time, value }],
                };
            }
            state.lastUpdated = time;
            if (locomotiveType) {
                state.locomotiveType = locomotiveType;
            }
        },
        gpsUpdated(state, action: PayloadAction<{ latitude: number; longitude: number }>) {
            state.gps = action.payload;
        },
        telemetryReset() {
            return initialState;
        },
    },
});

export const { sensorUpdated, gpsUpdated, telemetryReset } = telemetrySlice.actions;
export const telemetryReducer = telemetrySlice.reducer;
