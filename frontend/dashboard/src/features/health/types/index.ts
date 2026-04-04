export type HealthCategory = 'Норма' | 'Внимание' | 'Критично';

export interface HealthFactor {
    sensor_type: string;
    value: number;
    unit: string;
    penalty: number;
    contribution_pct: number;
    deviation_pct: number;
}

export interface HealthIndex {
    locomotive_id: string;
    locomotive_type: string;
    overall_score: number;
    category: HealthCategory;
    top_factors: HealthFactor[];
    damage_penalty: number;
    calculated_at: string;
}
