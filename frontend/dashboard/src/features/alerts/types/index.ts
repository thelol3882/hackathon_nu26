export type AlertSeverity = 'info' | 'warning' | 'critical' | 'emergency';

export interface AlertEvent {
    id: string;
    locomotive_id: string;
    sensor_type: string;
    severity: AlertSeverity;
    value: number;
    threshold_min: number | null;
    threshold_max: number | null;
    message: string;
    recommendation: string;
    timestamp: string;
    acknowledged: boolean;
}

export interface AlertsQuery {
    locomotive_id?: string;
    severity?: AlertSeverity;
    acknowledged?: boolean;
    start?: string;
    end?: string;
    offset?: number;
    limit?: number;
}
