import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from './store';

// Stable reference so RTK selectors don't re-compute downstream memos.
const EMPTY_ARRAY: Array<{ time: number; value: number }> = [];

export const selectCurrentValue = (sensorType: string) => (state: RootState) =>
    state.telemetry.sensors[sensorType]?.current ?? null;

export const selectSensorUnit = (sensorType: string) => (state: RootState) =>
    state.telemetry.sensors[sensorType]?.unit ?? null;

export const selectSensorHistory = (sensorType: string) => (state: RootState) =>
    state.telemetry.sensors[sensorType]?.history ?? EMPTY_ARRAY;

export const selectGps = (state: RootState) => state.telemetry.gps;

export const selectLocomotiveType = (state: RootState) =>
    state.telemetry.locomotiveType ?? state.health.locomotiveType;

export const selectLastUpdated = (state: RootState) => state.telemetry.lastUpdated;

export const selectSensorCount = (state: RootState) => Object.keys(state.telemetry.sensors).length;

export const selectHealthScore = (state: RootState) => state.health.overallScore;
export const selectHealthCategory = (state: RootState) => state.health.category;
export const selectTopFactors = (state: RootState) => state.health.topFactors;
export const selectDamagePenalty = (state: RootState) => state.health.damagePenalty;
export const selectHealthCalculatedAt = (state: RootState) => state.health.calculatedAt;

export const selectAlerts = (state: RootState) => state.alerts.items;
export const selectUnacknowledgedCount = (state: RootState) => state.alerts.unacknowledgedCount;

export const selectAlertsBySeverity = createSelector(selectAlerts, (alerts) => ({
    emergency: alerts.filter((a) => a.severity === 'emergency'),
    critical: alerts.filter((a) => a.severity === 'critical'),
    warning: alerts.filter((a) => a.severity === 'warning'),
    info: alerts.filter((a) => a.severity === 'info'),
}));
