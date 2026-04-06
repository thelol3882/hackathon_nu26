import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

const MAX_HISTORY = 300;

interface SensorData {
    current: number;
    unit: string;
    history: Array<{ time: number; value: number }>;
}

interface TelemetryState {
    sensors: Record<string, SensorData>;
    gps: {
        latitude: number;
        longitude: number;
        bearing_deg: number | null;
    } | null;
    locomotiveType: string | null;
    routeName: string | null;
    lastUpdated: number | null;
}

const initialState: TelemetryState = {
    sensors: {},
    gps: null,
    locomotiveType: null,
    routeName: null,
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
        gpsUpdated(
            state,
            action: PayloadAction<{
                latitude: number;
                longitude: number;
                bearing_deg?: number | null;
            }>,
        ) {
            state.gps = {
                latitude: action.payload.latitude,
                longitude: action.payload.longitude,
                bearing_deg: action.payload.bearing_deg ?? null,
            };
        },
        routeNameUpdated(state, action: PayloadAction<string | null>) {
            state.routeName = action.payload;
        },
        telemetryReset() {
            return initialState;
        },
    },
});

export const { sensorUpdated, gpsUpdated, routeNameUpdated, telemetryReset } =
    telemetrySlice.actions;
export const telemetryReducer = telemetrySlice.reducer;
