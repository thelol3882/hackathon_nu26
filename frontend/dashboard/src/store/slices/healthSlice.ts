import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

interface HealthFactor {
  sensor_type: string;
  value: number;
  unit: string;
  penalty: number;
  contribution_pct: number;
  deviation_pct: number;
}

interface HealthState {
  overallScore: number | null;
  category: string | null;
  locomotiveType: string | null;
  topFactors: HealthFactor[];
  damagePenalty: number;
  calculatedAt: string | null;
}

const initialState: HealthState = {
  overallScore: null,
  category: null,
  locomotiveType: null,
  topFactors: [],
  damagePenalty: 0,
  calculatedAt: null,
};

const healthSlice = createSlice({
  name: 'health',
  initialState,
  reducers: {
    healthUpdated(
      state,
      action: PayloadAction<{
        overall_score: number;
        category: string;
        locomotive_type?: string;
        top_factors: HealthFactor[];
        damage_penalty: number;
        calculated_at: string;
      }>,
    ) {
      const d = action.payload;
      state.overallScore = d.overall_score;
      state.category = d.category;
      state.locomotiveType = d.locomotive_type ?? state.locomotiveType;
      state.topFactors = d.top_factors;
      state.damagePenalty = d.damage_penalty;
      state.calculatedAt = d.calculated_at;
    },
    healthReset() {
      return initialState;
    },
  },
});

export const { healthUpdated, healthReset } = healthSlice.actions;
export const healthReducer = healthSlice.reducer;
