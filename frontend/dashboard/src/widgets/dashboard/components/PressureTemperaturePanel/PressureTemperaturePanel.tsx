'use client';

import {Card, Stack, Text} from '@mantine/core';
import type {TelemetryReading} from '@/features/telemetry/types';
import SensorRow from '@/widgets/dashboard/components/SensorRow';

interface PressureTemperaturePanelProps {
    coolantTemp?: TelemetryReading;
    oilPressure?: TelemetryReading;
    brakePipePressure?: TelemetryReading;
}

export default function PressureTemperaturePanel({
                                                     coolantTemp,
                                                     oilPressure,
                                                     brakePipePressure,
                                                 }: PressureTemperaturePanelProps) {
    return (
        <Card
            padding="md"
            radius="md"
            style={{borderTop: '2px solid var(--mantine-color-ktzCyan-5)'}}
        >
            <Stack gap="sm">
                <Text
                    size="xs"
                    fw={600}
                    c="var(--dashboard-text-secondary)"
                    style={{letterSpacing: '0.05em', textTransform: 'uppercase'}}
                >
                    ДАВЛЕНИЕ / ТЕМПЕРАТУРА
                </Text>

                <SensorRow
                    label="Охл. жидкость"
                    value={coolantTemp?.value ?? null}
                    unit="°C"
                    min={60}
                    max={110}
                    warningMin={70}
                    warningMax={95}
                />
                <SensorRow
                    label="Давл. масла"
                    value={oilPressure?.value ?? null}
                    unit="бар"
                    min={0}
                    max={8}
                    warningMin={1.5}
                    warningMax={5}
                />
                <SensorRow
                    label="Торм. магистраль"
                    value={brakePipePressure?.value ?? null}
                    unit="бар"
                    min={0}
                    max={10}
                    warningMin={4}
                    warningMax={6}
                />
            </Stack>
        </Card>
    );
}
