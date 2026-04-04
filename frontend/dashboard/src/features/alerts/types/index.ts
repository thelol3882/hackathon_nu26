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
    timestamp: string;
    acknowledged: boolean;
}

export interface AlertsQuery {
    locomotive_id?: string;
    severity?: AlertSeverity;
    acknowledged?: boolean;
    offset?: number;
    limit?: number;
}
