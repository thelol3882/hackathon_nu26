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
    position: { latitude: number; longitude: number } | null;
}

export function RouteMap({ position }: RouteMapProps) {
    return (
        <Card style={{ borderTop: '2px solid var(--mantine-color-ktzCyan-5)' }}>
            <Text className="panel-label" mb="sm">
                МАРШРУТ
            </Text>
            <RouteMapInner position={position} />
        </Card>
    );
}
