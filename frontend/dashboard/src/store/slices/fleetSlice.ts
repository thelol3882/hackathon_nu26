import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../store';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface WorstLocomotive {
    locomotive_id: string;
    locomotive_type: string;
    score: number;
    category: string;
}

interface FleetCategories {
    norma: number;
    vnimanie: number;
    kritichno: number;
}

/** Payload from the fleet:summary Redis channel. */
export interface FleetSummaryPayload {
    fleet_size: number;
    avg_score: number;
    categories: FleetCategories;
    worst_10: WorstLocomotive[];
    timestamp: string;
}

/** A single locomotive category change. */
interface FleetChange {
    locomotive_id: string;
    locomotive_type: string;
    old_category: string;
    new_category: string;
    score: number;
    timestamp: string;
}

/** Payload from the fleet:changes Redis channel. */
export interface FleetChangesPayload {
    changes: FleetChange[];
}

interface LocomotiveMapState {
    score: number;
    category: string;
    locomotiveType: string;
    updatedAt: number;
}

interface FleetState {
    fleetSize: number;
    avgScore: number;
    categories: FleetCategories;
    worst10: WorstLocomotive[];
    lastUpdated: number | null;
    /** Per-locomotive state for map markers — updated only via fleet:changes. */
    locomotiveStates: Record<string, LocomotiveMapState>;
}

const initialState: FleetState = {
    fleetSize: 0,
    avgScore: 0,
    categories: { norma: 0, vnimanie: 0, kritichno: 0 },
    worst10: [],
    lastUpdated: null,
    locomotiveStates: {},
};

/* ------------------------------------------------------------------ */
/*  Slice                                                              */
/* ------------------------------------------------------------------ */

const fleetSlice = createSlice({
    name: 'fleet',
    initialState,
    reducers: {
        /** Replace fleet summary stats (received every ~2 seconds). */
        fleetSummaryUpdated(state, action: PayloadAction<FleetSummaryPayload>) {
            const { fleet_size, avg_score, categories, worst_10, timestamp } = action.payload;
            state.fleetSize = fleet_size;
            state.avgScore = avg_score;
            state.categories = categories;
            state.worst10 = worst_10;
            state.lastUpdated = new Date(timestamp).getTime();
        },

        /** Apply category changes to per-locomotive map state. */
        fleetChangesReceived(state, action: PayloadAction<FleetChangesPayload>) {
            for (const change of action.payload.changes) {
                state.locomotiveStates[change.locomotive_id] = {
                    score: change.score,
                    category: change.new_category,
                    locomotiveType: change.locomotive_type,
                    updatedAt: new Date(change.timestamp).getTime(),
                };
            }
        },

        fleetReset() {
            return initialState;
        },
    },
});

export const { fleetSummaryUpdated, fleetChangesReceived, fleetReset } = fleetSlice.actions;
export const fleetReducer = fleetSlice.reducer;

/* ------------------------------------------------------------------ */
/*  Selectors                                                          */
/* ------------------------------------------------------------------ */

export const selectFleetCategories = (state: RootState) => state.fleet.categories;
export const selectFleetAvgScore = (state: RootState) => state.fleet.avgScore;
export const selectFleetSize = (state: RootState) => state.fleet.fleetSize;
export const selectWorst10 = (state: RootState) => state.fleet.worst10;
export const selectFleetLastUpdated = (state: RootState) => state.fleet.lastUpdated;
export const selectLocomotiveState = (locoId: string) => (state: RootState) =>
    state.fleet.locomotiveStates[locoId];
