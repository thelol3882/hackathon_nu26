/**
 * Types for the operator-driven locomotive simulator.
 *
 * The dashboard talks to the simulator through `/api/simulator/...`
 * which is just a thin pass-through over the simulator service. The
 * shapes below mirror the Pydantic DTOs in
 * `services/simulator/main.py` (LocomotiveStateDTO,
 * CreateLocomotiveRequest, UpdateLocomotiveRequest).
 */

export type LocomotiveType = 'TE33A' | 'KZ8A';

export type LocomotiveMode =
    | 'depot'
    | 'departure'
    | 'cruising'
    | 'arrival'
    | 'aess_sleep'
    | 'emergency'
    | 'recovery';

export type LocomotiveScenario = 'normal' | 'degradation' | 'emergency';

export type OnArrival = 'loop' | 'stop' | 'remove';

export interface SimulatedLocomotive {
    id: string;
    name: string;
    loco_type: LocomotiveType;
    route_name: string;
    mode: LocomotiveMode;
    scenario: LocomotiveScenario;
    auto_mode: boolean;
    on_arrival: OnArrival;
    speed_kmh: number;
    forward: boolean;
    distance_km: number;
    start_km: number;
    end_km: number;
    segment_progress: number;
    lat: number;
    lon: number;
    bearing_deg: number;
}

export interface CreateSimulatedLocomotiveBody {
    id: string; // catalogue UUID — must already exist in /locomotives
    loco_type: LocomotiveType;
    route_name: string;
    name?: string;
    start_station?: string | null;
    end_station?: string | null;
    mode?: LocomotiveMode;
    scenario?: LocomotiveScenario;
    on_arrival?: OnArrival;
    auto_mode?: boolean;
    initial_speed_kmh?: number;
}

export interface UpdateSimulatedLocomotiveBody {
    name?: string;
    route_name?: string;
    start_station?: string | null;
    end_station?: string | null;
    mode?: LocomotiveMode;
    scenario?: LocomotiveScenario;
    on_arrival?: OnArrival;
    auto_mode?: boolean;
    speed_kmh?: number;
}
