import { useAppSelector } from '@/store/hooks';
import { healthApi } from '../api/healthApi';
import type { HealthIndex } from '../types';

/**
 * Returns the health index for a locomotive.
 * Primary: reads from Redux (populated by useWsDispatch in DashboardPage).
 * Fallback: REST query on initial load.
 */
export function useHealthIndex(locomotiveId: string | null) {
    const {
        data: restHealth,
        isLoading,
        error,
    } = healthApi.useGetHealthQuery(locomotiveId ?? '', { skip: !locomotiveId });

    const overallScore = useAppSelector((state) => state.health.overallScore);
    const category = useAppSelector((state) => state.health.category);
    const locomotiveType = useAppSelector((state) => state.health.locomotiveType);
    const topFactors = useAppSelector((state) => state.health.topFactors);
    const damagePenalty = useAppSelector((state) => state.health.damagePenalty);
    const calculatedAt = useAppSelector((state) => state.health.calculatedAt);

    // If we have live WS data in Redux, prefer it; otherwise fall back to REST
    const liveHealth: HealthIndex | null =
        overallScore !== null && category !== null
            ? {
                  locomotive_id: locomotiveId ?? '',
                  locomotive_type: locomotiveType ?? '',
                  overall_score: overallScore,
                  category: category as HealthIndex['category'],
                  top_factors: topFactors,
                  damage_penalty: damagePenalty,
                  calculated_at: calculatedAt ?? '',
              }
            : null;

    const health = liveHealth ?? restHealth ?? null;

    // connectionStatus no longer needed here — useWsDispatch handles it
    return { health, isLoading, connectionStatus: 'connected' as const, error };
}
