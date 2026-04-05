import { useEffect, useRef, useState } from 'react';
import { store } from '@/store/store';

const EMPTY: Array<{ time: number; value: number }> = [];

/**
 * Reads sensor history from Redux store via ref (no subscription),
 * and copies it into React state at a throttled interval.
 *
 * This limits Recharts SVG re-renders to once per intervalMs
 * instead of on every WS message.
 *
 * Usage:
 *   const chartData = useThrottledHistory('coolant_temp', 1000)
 *   return <LineChart data={chartData} />
 */
export function useThrottledHistory(
  sensorType: string,
  intervalMs: number = 1000,
): Array<{ time: number; value: number }> {
  const [chartData, setChartData] = useState<Array<{ time: number; value: number }>>(EMPTY);
  const storeRef = useRef(store);

  useEffect(() => {
    // Read immediately on mount
    const state = storeRef.current.getState();
    const history = state.telemetry.sensors[sensorType]?.history;
    if (history && history.length > 0) {
      setChartData(history);
    }

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
