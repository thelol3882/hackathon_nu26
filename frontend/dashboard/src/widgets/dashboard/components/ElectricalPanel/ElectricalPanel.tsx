'use client';

import { Card, Stack, Text } from '@mantine/core';
import type { TelemetryReading } from '@/features/telemetry/types';
import SensorRow from '@/widgets/dashboard/components/SensorRow';

interface ElectricalPanelProps {
    locomotiveType: string | undefined;
    // TE33A
    tractionMotorTemp?: TelemetryReading;
    crankcasePressure?: TelemetryReading;
    dieselRpm?: TelemetryReading;
    // KZ8A
    transformerTemp?: TelemetryReading;
    igbtTemp?: TelemetryReading;
    dcLinkVoltage?: TelemetryReading;
    recuperationCurrent?: TelemetryReading;
}

export default function ElectricalPanel({
    locomotiveType,
    tractionMotorTemp,
    crankcasePressure,
    dieselRpm,
    transformerTemp,
    igbtTemp,
    dcLinkVoltage,
    recuperationCurrent,
}: ElectricalPanelProps) {
    const isDiesel = locomotiveType === 'TE33A';

    return (
        <Card
            padding="md"
            radius="md"
            style={{ borderTop: '2px solid var(--mantine-color-healthy-5)' }}
        >
            <Stack gap="sm">
                <Text
                    size="xs"
                    fw={600}
                    c="var(--dashboard-text-secondary)"
                    style={{ letterSpacing: '0.05em', textTransform: 'uppercase' }}
                >
                    ТЯГОВАЯ СИСТЕМА
                </Text>

                {isDiesel ? (
                    <>
                        <SensorRow
                            label="Тяговый двигатель"
                            value={tractionMotorTemp?.value ?? null}
                            unit="°C"
                            min={0}
                            max={200}
                            warningMin={0}
                            warningMax={150}
                        />
                        <SensorRow
                            label="Давл. картера"
                            value={crankcasePressure?.value ?? null}
                            unit="Па"
                            min={0}
                            max={500}
                            warningMin={0}
                            warningMax={250}
                        />
                        <SensorRow
                            label="Обороты дизеля"
                            value={dieselRpm?.value ?? null}
                            unit="об/мин"
                            min={0}
                            max={1050}
                            warningMin={400}
                            warningMax={900}
                        />
                    </>
                ) : (
                    <>
                        <SensorRow
                            label="Трансформатор"
                            value={transformerTemp?.value ?? null}
                            unit="°C"
                            min={0}
                            max={150}
                            warningMin={0}
                            warningMax={120}
                        />
                        <SensorRow
                            label="IGBT модуль"
                            value={igbtTemp?.value ?? null}
                            unit="°C"
                            min={0}
                            max={150}
                            warningMin={0}
                            warningMax={100}
                        />
                        <SensorRow
                            label="Напр. DC звена"
                            value={dcLinkVoltage?.value ?? null}
                            unit="В"
                            min={0}
                            max={4000}
                            warningMin={2500}
                            warningMax={3500}
                        />
                        <SensorRow
                            label="Ток рекуперации"
                            value={recuperationCurrent?.value ?? null}
                            unit="А"
                            min={0}
                            max={500}
                        />
                    </>
                )}
            </Stack>
        </Card>
    );
}
