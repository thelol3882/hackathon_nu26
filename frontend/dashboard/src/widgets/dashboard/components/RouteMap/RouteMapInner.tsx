'use client';

// Live locomotive map. The marker tweens between GPS samples via rAF
// (samples arrive ~1Hz) so motion looks continuous. The active route
// polyline and stations are loaded once from /routes.

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import {
    MapContainer,
    TileLayer,
    Marker,
    Polyline,
    Popup,
    CircleMarker,
    useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useMantineColorScheme, Group, Text, ActionIcon, Tooltip, Badge } from '@mantine/core';
import { IconFocus2, IconRoute } from '@tabler/icons-react';
import classes from './RouteMap.module.css';
import { useGetRoutesQuery } from '@/features/routes';

interface PositionShape {
    latitude: number;
    longitude: number;
    bearing_deg: number | null;
}

interface RouteMapInnerProps {
    position: PositionShape | null;
    routeName: string | null;
    speedKmh: number | null;
}

const KZ_CENTER: [number, number] = [48.0, 67.0];
const KZ_ZOOM = 6;
const POSITION_ZOOM = 8;
const MAX_TRAIL_POINTS = 200;
// Roughly matches WS publish interval (~1s); slightly less for snappier feel.
const MARKER_TWEEN_MS = 950;

const DARK_TILES = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const LIGHT_TILES = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';

const trainIcon = L.divIcon({
    html: `<div style="
        width:20px;height:20px;
        background:var(--mantine-color-ktzBlue-5,#0388e6);
        border:3px solid #fff;
        border-radius:50%;
        box-shadow:0 0 12px rgba(3,136,230,0.6), 0 2px 6px rgba(0,0,0,0.35);
    "></div>`,
    className: '',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
});

function MapUpdater({
    position,
    followMode,
    centerTrigger,
    onFirstPosition,
    onUserDrag,
}: {
    position: { latitude: number; longitude: number } | null;
    followMode: boolean;
    centerTrigger: number;
    onFirstPosition: () => void;
    onUserDrag: () => void;
}) {
    const map = useMap();
    const hasInitialized = useRef(false);

    useEffect(() => {
        const handler = () => onUserDrag();
        map.on('dragstart', handler);
        return () => {
            map.off('dragstart', handler);
        };
    }, [map, onUserDrag]);

    useEffect(() => {
        if (!position) return;

        if (!hasInitialized.current) {
            map.setView([position.latitude, position.longitude], POSITION_ZOOM);
            hasInitialized.current = true;
            onFirstPosition();
            return;
        }

        if (followMode) {
            map.panTo([position.latitude, position.longitude], { animate: true, duration: 0.5 });
        }
    }, [map, position, followMode, onFirstPosition]);

    useEffect(() => {
        if (centerTrigger > 0 && position) {
            map.flyTo([position.latitude, position.longitude], POSITION_ZOOM, { duration: 0.8 });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [centerTrigger]);

    return null;
}

// rAF tween between GPS samples. Snaps on the first fix, linearly interpolates after.
function useSmoothPosition(
    target: { latitude: number; longitude: number } | null,
): [number, number] | null {
    const [displayed, setDisplayed] = useState<[number, number] | null>(null);
    const fromRef = useRef<[number, number] | null>(null);
    const toRef = useRef<[number, number] | null>(null);
    const startRef = useRef<number>(0);
    const rafRef = useRef<number | null>(null);

    useEffect(() => {
        if (!target) return;
        const next: [number, number] = [target.latitude, target.longitude];

        if (!displayed) {
            // First fix: snap without animation.
            fromRef.current = next;
            toRef.current = next;
            setDisplayed(next);
            return;
        }

        // Snapshot fromRef from the currently displayed value (not the previous
        // target) so interrupting a tween mid-animation doesn't teleport.
        fromRef.current = displayed;
        toRef.current = next;
        startRef.current = performance.now();

        const tick = (now: number) => {
            const from = fromRef.current;
            const to = toRef.current;
            if (!from || !to) return;
            const t = Math.min(1, (now - startRef.current) / MARKER_TWEEN_MS);
            const lat = from[0] + (to[0] - from[0]) * t;
            const lon = from[1] + (to[1] - from[1]) * t;
            setDisplayed([lat, lon]);
            if (t < 1) {
                rafRef.current = requestAnimationFrame(tick);
            }
        };
        if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
        rafRef.current = requestAnimationFrame(tick);

        return () => {
            if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
        };
        // Deliberately excluding `displayed` — it would restart the tween every frame.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [target?.latitude, target?.longitude]);

    return displayed;
}

const COMPASS_LABELS = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'];

function bearingToCompass(deg: number | null | undefined): string {
    if (deg == null) return '—';
    const idx = Math.round(deg / 45) % 8;
    return `${COMPASS_LABELS[idx]} (${Math.round(deg)}°)`;
}

export default function RouteMapInner({ position, routeName, speedKmh }: RouteMapInnerProps) {
    const { colorScheme } = useMantineColorScheme();
    const tileUrl = colorScheme === 'dark' ? DARK_TILES : LIGHT_TILES;

    const [followMode, setFollowMode] = useState(true);
    const [showTrail, setShowTrail] = useState(true);
    const [trail, setTrail] = useState<[number, number][]>([]);
    const prevPosKey = useRef<string | null>(null);

    // Marker reads the tween; trail and follow-camera read raw `position`
    // so they update on sample boundaries instead of every rAF tick.
    const displayPos = useSmoothPosition(position);

    const { data: routes } = useGetRoutesQuery();
    const activeRoute = useMemo(
        () => routes?.find((r) => r.name === routeName) ?? null,
        [routes, routeName],
    );

    // Append GPS to trail and atomically reset on route change (one effect, no cascading setState).
    const prevRouteRef = useRef<string | null>(routeName);
    useEffect(() => {
        if (!position) return;
        const key = `${position.latitude.toFixed(6)},${position.longitude.toFixed(6)}`;
        if (key === prevPosKey.current) return;
        prevPosKey.current = key;
        const pt: [number, number] = [position.latitude, position.longitude];
        const routeChanged = prevRouteRef.current !== routeName;
        prevRouteRef.current = routeName;
        const timer = setTimeout(() => {
            setTrail((prev) => {
                const base = routeChanged ? [] : prev;
                const next = [...base, pt];
                return next.length > MAX_TRAIL_POINTS ? next.slice(-MAX_TRAIL_POINTS) : next;
            });
        }, 0);
        return () => clearTimeout(timer);
    }, [position, routeName]);

    const handleFirstPosition = useCallback(() => {
        setFollowMode(true);
    }, []);

    const handleUserDrag = useCallback(() => {
        setFollowMode(false);
    }, []);

    const [centerTrigger, setCenterTrigger] = useState(0);

    const handleCenterOnTrain = useCallback(() => {
        setFollowMode(true);
        setCenterTrigger((n) => n + 1);
    }, []);

    return (
        <div className={classes.mapContainer}>
            <Group gap={4} className={classes.mapControls}>
                <Tooltip label={followMode ? 'Следит за поездом' : 'Центрировать на поезде'}>
                    <ActionIcon
                        variant={followMode ? 'filled' : 'light'}
                        color="ktzBlue"
                        size="sm"
                        onClick={handleCenterOnTrain}
                    >
                        <IconFocus2 size={14} />
                    </ActionIcon>
                </Tooltip>
                <Tooltip label={showTrail ? 'Скрыть маршрут' : 'Показать маршрут'}>
                    <ActionIcon
                        variant={showTrail ? 'filled' : 'light'}
                        color="ktzCyan"
                        size="sm"
                        onClick={() => setShowTrail(!showTrail)}
                    >
                        <IconRoute size={14} />
                    </ActionIcon>
                </Tooltip>
                {trail.length > 0 && (
                    <Badge size="xs" variant="light" color="ktzCyan">
                        {trail.length} точек
                    </Badge>
                )}
                {activeRoute && (
                    <Badge size="xs" variant="light" color="ktzBlue">
                        {activeRoute.name} · {activeRoute.length_km.toFixed(0)} км
                    </Badge>
                )}
            </Group>

            {position && (
                <div className={classes.coordDisplay}>
                    <Text size="xs" ff="var(--font-mono), monospace" c="dimmed">
                        {position.latitude.toFixed(5)}, {position.longitude.toFixed(5)}
                    </Text>
                </div>
            )}

            <MapContainer
                center={KZ_CENTER}
                zoom={KZ_ZOOM}
                style={{ height: 350, width: '100%' }}
                scrollWheelZoom
                whenReady={() => {}}
            >
                <TileLayer
                    attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                    url={tileUrl}
                />
                <MapUpdater
                    position={position}
                    followMode={followMode}
                    centerTrigger={centerTrigger}
                    onFirstPosition={handleFirstPosition}
                    onUserDrag={handleUserDrag}
                />

                {showTrail && activeRoute && activeRoute.waypoints.length > 1 && (
                    <Polyline
                        positions={activeRoute.waypoints}
                        pathOptions={{
                            color: 'var(--mantine-color-ktzBlue-5)',
                            weight: 2,
                            opacity: 0.45,
                            dashArray: '4, 6',
                        }}
                    />
                )}

                {showTrail &&
                    activeRoute?.stations.map((s) => (
                        <CircleMarker
                            key={`${activeRoute.name}-${s.km_from_start}`}
                            center={[s.lat, s.lon]}
                            radius={4}
                            pathOptions={{
                                color: 'var(--mantine-color-ktzGold-5)',
                                fillColor: 'var(--mantine-color-ktzGold-5)',
                                fillOpacity: 0.85,
                                weight: 1,
                            }}
                        >
                            <Popup>
                                <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                                    <strong>{s.name}</strong>
                                    <br />
                                    {s.km_from_start.toFixed(0)} км от начала
                                </div>
                            </Popup>
                        </CircleMarker>
                    ))}

                {showTrail && trail.length > 1 && (
                    <Polyline
                        positions={trail}
                        pathOptions={{
                            color: 'var(--mantine-color-ktzCyan-5)',
                            weight: 3,
                            opacity: 0.75,
                            dashArray: '8, 4',
                        }}
                    />
                )}

                {displayPos && (
                    <Marker position={displayPos} icon={trainIcon}>
                        <Popup>
                            <div style={{ fontSize: 12, lineHeight: 1.6, minWidth: 180 }}>
                                <strong>Текущее положение</strong>
                                {routeName && (
                                    <>
                                        <br />
                                        <span style={{ color: '#888' }}>Маршрут: </span>
                                        {routeName}
                                    </>
                                )}
                                {speedKmh != null && (
                                    <>
                                        <br />
                                        <span style={{ color: '#888' }}>Скорость: </span>
                                        {speedKmh.toFixed(1)} км/ч
                                    </>
                                )}
                                <br />
                                <span style={{ color: '#888' }}>Курс: </span>
                                {bearingToCompass(position?.bearing_deg)}
                                <br />
                                <span style={{ color: '#888' }}>Шир: </span>
                                {position?.latitude.toFixed(5)}
                                <br />
                                <span style={{ color: '#888' }}>Долг: </span>
                                {position?.longitude.toFixed(5)}
                            </div>
                        </Popup>
                    </Marker>
                )}
            </MapContainer>
        </div>
    );
}
