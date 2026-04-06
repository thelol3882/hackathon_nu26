/** Static railway route metadata from the api-gateway /routes endpoint. Geometry is deployment-constant, so fetched once per session. */

export type LatLon = [number, number];

export interface RouteStation {
    name: string;
    lat: number;
    lon: number;
    km_from_start: number;
}

export interface RouteInfo {
    name: string;
    electrified: boolean;
    length_km: number;
    waypoints: LatLon[];
    stations: RouteStation[];
}
