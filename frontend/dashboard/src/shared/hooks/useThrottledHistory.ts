import { useEffect, useMemo, useRef, useState } from 'react';
import { store } from '@/store/store';

const EMPTY: Array<{ time: number; value: number }> = [];

/** Polls sensor history from the store on an interval to throttle chart re-renders. */
export function useThrottledHistory(
    sensorType: string,
    intervalMs: number = 1000,
): Array<{ time: number; value: number }> {
    // Read initial value synchronously to avoid "setState in effect body" lint error.
    const initialData = useMemo(() => {
        const state = store.getState();
        const history = state.telemetry.sensors[sensorType]?.history;
        return history && history.length > 0 ? history : EMPTY;
    }, [sensorType]);

    const [chartData, setChartData] = useState(initialData);
    const storeRef = useRef(store);

    useEffect(() => {
        const interval = setInterval(() => {
            const state = storeRef.current.getState();
            const history = state.telemetry.sensors[sensorType]?.history;
            if (history) {
                setChartData(history);
            }
        }, intervalMs);

        return () => clearInterval(interval);
    }, [sensorType, intervalMs]);

    return chartData;
}
