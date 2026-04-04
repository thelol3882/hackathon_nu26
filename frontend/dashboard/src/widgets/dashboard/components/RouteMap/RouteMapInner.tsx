'use client';

import { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useMantineColorScheme } from '@mantine/core';
import classes from './RouteMap.module.css';

interface RouteMapInnerProps {
    position: { latitude: number; longitude: number } | null;
}

const KZ_CENTER: [number, number] = [48.0, 67.0];
const KZ_ZOOM = 6;
const POSITION_ZOOM = 12;

const DARK_TILES = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const LIGHT_TILES = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';

const trainIcon = L.divIcon({
    html: '<div style="width:24px;height:24px;background:var(--mantine-color-ktzBlue-5,#0054A6);border:2px solid #fff;border-radius:50%;box-shadow:0 2px 6px rgba(0,0,0,0.35);"></div>',
    className: '',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
});

function MapUpdater({ position }: { position: { latitude: number; longitude: number } | null }) {
    const map = useMap();
    const prevPosition = useRef<{ latitude: number; longitude: number } | null>(null);

    useEffect(() => {
        if (position) {
            const prev = prevPosition.current;
            if (
                !prev ||
                prev.latitude !== position.latitude ||
                prev.longitude !== position.longitude
            ) {
                map.flyTo([position.latitude, position.longitude], POSITION_ZOOM);
                prevPosition.current = position;
            }
        }
    }, [map, position]);

    return null;
}

export default function RouteMapInner({ position }: RouteMapInnerProps) {
    const { colorScheme } = useMantineColorScheme();
    const tileUrl = colorScheme === 'dark' ? DARK_TILES : LIGHT_TILES;

    return (
        <div className={classes.mapContainer}>
            <MapContainer
                center={KZ_CENTER}
                zoom={KZ_ZOOM}
                style={{ height: 300, width: '100%' }}
                scrollWheelZoom
            >
                <TileLayer
                    attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                    url={tileUrl}
                />
                <MapUpdater position={position} />
                {position && (
                    <Marker
                        position={[position.latitude, position.longitude]}
                        icon={trainIcon}
                    />
                )}
            </MapContainer>
        </div>
    );
}
