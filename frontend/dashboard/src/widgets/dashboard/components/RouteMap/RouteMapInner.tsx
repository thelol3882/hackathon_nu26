'use client';

import {useEffect, useRef, useState, useCallback} from 'react';
import {MapContainer, TileLayer, Marker, Polyline, Popup, useMap} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {useMantineColorScheme, Group, Text, ActionIcon, Tooltip, Badge} from '@mantine/core';
import {IconFocus2, IconRoute} from '@tabler/icons-react';
import classes from './RouteMap.module.css';

interface RouteMapInnerProps {
    position: { latitude: number; longitude: number } | null;
}

const KZ_CENTER: [number, number] = [48.0, 67.0];
const KZ_ZOOM = 6;
const POSITION_ZOOM = 13;
const MAX_TRAIL_POINTS = 200;

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
            map.panTo([position.latitude, position.longitude], {animate: true, duration: 0.5});
        }
    }, [map, position, followMode, onFirstPosition]);

    useEffect(() => {
        if (centerTrigger > 0 && position) {
            map.flyTo([position.latitude, position.longitude], POSITION_ZOOM, {duration: 0.8});
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [centerTrigger]);

    return null;
}

export default function RouteMapInner({position}: RouteMapInnerProps) {
    const {colorScheme} = useMantineColorScheme();
    const tileUrl = colorScheme === 'dark' ? DARK_TILES : LIGHT_TILES;

    const [followMode, setFollowMode] = useState(true);
    const [showTrail, setShowTrail] = useState(true);
    const [trail, setTrail] = useState<[number, number][]>([]);
    const prevPosKey = useRef<string | null>(null);

    useEffect(() => {
        if (!position) return;
        const key = `${position.latitude.toFixed(6)},${position.longitude.toFixed(6)}`;
        if (key === prevPosKey.current) return;
        prevPosKey.current = key;
        const pt: [number, number] = [position.latitude, position.longitude];
        const timer = setTimeout(() => {
            setTrail((prev) => {
                const next = [...prev, pt];
                return next.length > MAX_TRAIL_POINTS ? next.slice(-MAX_TRAIL_POINTS) : next;
            });
        }, 0);
        return () => clearTimeout(timer);
    }, [position]);

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
                        <IconFocus2 size={14}/>
                    </ActionIcon>
                </Tooltip>
                <Tooltip label={showTrail ? 'Скрыть маршрут' : 'Показать маршрут'}>
                    <ActionIcon
                        variant={showTrail ? 'filled' : 'light'}
                        color="ktzCyan"
                        size="sm"
                        onClick={() => setShowTrail(!showTrail)}
                    >
                        <IconRoute size={14}/>
                    </ActionIcon>
                </Tooltip>
                {trail.length > 0 && (
                    <Badge size="xs" variant="light" color="ktzCyan">
                        {trail.length} точек
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
                style={{height: 350, width: '100%'}}
                scrollWheelZoom
                whenReady={() => {
                }}
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

                {showTrail && trail.length > 1 && (
                    <Polyline
                        positions={trail}
                        pathOptions={{
                            color: 'var(--mantine-color-ktzCyan-5)',
                            weight: 3,
                            opacity: 0.7,
                            dashArray: '8, 4',
                        }}
                    />
                )}

                {position && (
                    <Marker position={[position.latitude, position.longitude]} icon={trainIcon}>
                        <Popup>
                            <div style={{fontSize: 12, lineHeight: 1.6}}>
                                <strong>Текущее положение</strong>
                                <br/>
                                Шир: {position.latitude.toFixed(5)}
                                <br/>
                                Долг: {position.longitude.toFixed(5)}
                            </div>
                        </Popup>
                    </Marker>
                )}
            </MapContainer>
        </div>
    );
}
