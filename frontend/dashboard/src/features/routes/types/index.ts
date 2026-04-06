/**
 * Static railway route metadata served by the api-gateway /routes endpoint.
 *
 * The polyline geometry is generated server-side at process boot from
 * `shared/route_geometry.py` and never changes for the lifetime of a
 * deployment, so this data is fetched once and reused for the whole
 * dashboard session (see `useGetRoutesQuery`).
 */

/** A single point on the route polyline encoded as `[lat, lon]`. */
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
