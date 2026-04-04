export type LocomotiveStatus = 'active' | 'idle' | 'maintenance' | 'decommissioned';

export interface Locomotive {
    id: string;
    serial_number: string;
    model: string;
    manufacturer: string;
    year_manufactured: number;
    status: LocomotiveStatus;
    created_at: string;
    updated_at: string;
}

export interface LocomotiveCreate {
    serial_number: string;
    model: string;
    manufacturer: string;
    year_manufactured: number;
}

export interface LocomotiveListResponse {
    items: Locomotive[];
    total: number;
}

export interface LocomotiveQueryParams {
    offset?: number;
    limit?: number;
    search?: string;
    model?: string;
}
