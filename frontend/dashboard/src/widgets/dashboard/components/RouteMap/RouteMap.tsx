'use client';

import dynamic from 'next/dynamic';
import { Card, Text, Loader, Center } from '@mantine/core';

const RouteMapInner = dynamic(() => import('./RouteMapInner'), {
    ssr: false,
    loading: () => (
        <Center h={300}>
            <Loader size="sm" />
        </Center>
    ),
});

interface RouteMapProps {
    position: {
        latitude: number;
        longitude: number;
        bearing_deg: number | null;
    } | null;
    routeName: string | null;
    speedKmh: number | null;
}

export function RouteMap({ position, routeName, speedKmh }: RouteMapProps) {
    return (
        <Card style={{ borderTop: '2px solid var(--mantine-color-ktzCyan-5)' }}>
            <Text className="panel-label" mb="sm">
                МАРШРУТ
            </Text>
            <RouteMapInner position={position} routeName={routeName} speedKmh={speedKmh} />
        </Card>
    );
}
