'use client';

import { Card, Stack, Text, Group } from '@mantine/core';
import type { TelemetryReading } from '@/features/telemetry/types';
import SensorRow from '@/widgets/dashboard/components/SensorRow';

interface FuelEnergyPanelProps {
    locomotiveType: string | undefined;
    fuelLevel?: TelemetryReading;
    fuelRate?: TelemetryReading;
    catenaryVoltage?: TelemetryReading;
    pantographCurrent?: TelemetryReading;
}

export default function FuelEnergyPanel({
    locomotiveType,
    fuelLevel,
    fuelRate,
    catenaryVoltage,
    pantographCurrent,
}: FuelEnergyPanelProps) {
    const isDiesel = locomotiveType === 'TE33A';
    const panelLabel = isDiesel ? 'ТОПЛИВО' : 'ЭЛЕКТРОПИТАНИЕ';

    const fuelLevelValue = fuelLevel?.value ?? null;
    const fuelLevelPercent =
        fuelLevelValue !== null ? Math.min(100, Math.max(0, fuelLevelValue)) : 0;

    let fuelBarColor = 'var(--mantine-color-healthy-5)';
    if (fuelLevelValue !== null) {
        if (fuelLevelValue < 15) fuelBarColor = 'var(--mantine-color-critical-5)';
        else if (fuelLevelValue < 30) fuelBarColor = 'var(--mantine-color-ktzGold-5)';
    }

    return (
        <Card
            padding="md"
            radius="md"
            style={{ borderTop: '2px solid var(--mantine-color-ktzGold-5)' }}
        >
            <Stack gap="sm">
                <Text
                    size="xs"
                    fw={600}
                    c="var(--dashboard-text-secondary)"
                    style={{ letterSpacing: '0.05em', textTransform: 'uppercase' }}
                >
                    {panelLabel}
                </Text>

                {isDiesel ? (
                    <>
                        {/* Fuel level vertical bar */}
                        <Group gap="md" align="flex-end">
                            <Stack gap={4} align="center" style={{ width: 48 }}>
                                <Text size="xs" c="var(--dashboard-text-secondary)">
                                    Уровень
                                </Text>
                                <div
                                    style={{
                                        width: 32,
                                        height: 80,
                                        borderRadius: 4,
                                        background: 'var(--mantine-color-dark-6)',
                                        position: 'relative',
                                        overflow: 'hidden',
                                    }}
                                >
                                    <div
                                        style={{
                                            position: 'absolute',
                                            bottom: 0,
                                            left: 0,
                                            right: 0,
                                            height: `${fuelLevelPercent}%`,
                                            background: fuelBarColor,
                                            borderRadius: '0 0 4px 4px',
                                            transition: 'height 0.3s ease',
                                        }}
                                    />
                                </div>
                                <span
                                    className="instrument-value"
                                    style={{
                                        fontFamily: 'var(--font-mono, monospace)',
                                        fontSize: 14,
                                    }}
                                >
                                    {fuelLevelValue !== null
                                        ? `${fuelLevelValue.toFixed(0)}%`
                                        : '--%'}
                                </span>
                            </Stack>
                            <Stack gap="sm" style={{ flex: 1 }}>
                                <SensorRow
                                    label="Расход"
                                    value={fuelRate?.value ?? null}
                                    unit="л/ч"
                                    min={0}
                                    max={500}
                                />
                            </Stack>
                        </Group>
                    </>
                ) : (
                    <>
                        <SensorRow
                            label="Напряжение"
                            value={catenaryVoltage?.value ?? null}
                            unit="кВ"
                            min={20}
                            max={30}
                            warningMin={23}
                            warningMax={27}
                        />
                        <SensorRow
                            label="Ток пантографа"
                            value={pantographCurrent?.value ?? null}
                            unit="А"
                            min={0}
                            max={1000}
                        />
                    </>
                )}
            </Stack>
        </Card>
    );
}
