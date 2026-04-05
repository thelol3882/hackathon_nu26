export type TE33ASensorType =
    | 'diesel_rpm'
    | 'oil_pressure'
    | 'coolant_temp'
    | 'fuel_level'
    | 'fuel_rate'
    | 'traction_motor_temp'
    | 'crankcase_pressure';
export type KZ8ASensorType =
    | 'catenary_voltage'
    | 'pantograph_current'
    | 'transformer_temp'
    | 'igbt_temp'
    | 'recuperation_current'
    | 'dc_link_voltage';
export type CommonSensorType =
    | 'speed_actual'
    | 'speed_target'
    | 'brake_pipe_pressure'
    | 'wheel_slip_ratio';
export type SensorType = TE33ASensorType | KZ8ASensorType | CommonSensorType;

export interface TelemetryReading {
    locomotive_id: string;
    locomotive_type: string;
    sensor_type: SensorType;
    value: number;
    filtered_value: number | null;
    unit: string;
    timestamp: string;
    latitude: number | null;
    longitude: number | null;
}

export interface TelemetryBucket {
    bucket: string;
    locomotive_id: string;
    sensor_type: string;
    avg_value: number | null;
    min_value: number | null;
    max_value: number | null;
    last_value: number | null;
    unit: string;
}

export type BucketInterval =
    | '1 minute'
    | '5 minutes'
    | '10 minutes'
    | '15 minutes'
    | '30 minutes'
    | '1 hour'
    | '1 day';

export interface TelemetryQuery {
    locomotive_id?: string;
    sensor_type?: string;
    start?: string;
    end?: string;
    bucket_interval?: BucketInterval;
    offset?: number;
    limit?: number;
}

export interface TelemetrySnapshotItem {
    locomotive_id: string;
    locomotive_type: string;
    sensor_type: SensorType;
    value: number;
    filtered_value: number | null;
    unit: string;
    timestamp: string;
    latitude: number | null;
    longitude: number | null;
}

export interface TelemetryRawQuery {
    locomotive_id?: string;
    sensor_type?: string;
    start?: string;
    end?: string;
    offset?: number;
    limit?: number;
}
