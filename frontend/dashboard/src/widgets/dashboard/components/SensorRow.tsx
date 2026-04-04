'use client';

import { Group, Text, Progress, Stack } from '@mantine/core';

interface SensorRowProps {
    label: string;
    value: number | null;
    unit: string;
    min?: number;
    max?: number;
    warningMin?: number;
    warningMax?: number;
}

function getProgressColor(
    value: number | null,
    min: number,
    max: number,
    warningMin?: number,
    warningMax?: number,
): string {
    if (value === null) return 'gray';
    if (value < min || value > max) return 'var(--mantine-color-critical-5)';
    if (warningMin !== undefined && warningMax !== undefined) {
        if (value >= warningMin && value <= warningMax) {
            return 'var(--mantine-color-healthy-5)';
        }
        return 'var(--mantine-color-ktzGold-5)';
    }
    return 'var(--mantine-color-healthy-5)';
}

function clamp(val: number, lo: number, hi: number): number {
    return Math.min(hi, Math.max(lo, val));
}

export default function SensorRow({
    label,
    value,
    unit,
    min = 0,
    max = 100,
    warningMin,
    warningMax,
}: SensorRowProps) {
    const percentage =
        value === null ? 0 : clamp(((value - min) / (max - min)) * 100, 0, 100);

    const color = getProgressColor(value, min, max, warningMin, warningMax);

    return (
        <Stack gap={4}>
            <Group justify="space-between" wrap="nowrap">
                <Text size="xs" c="var(--dashboard-text-secondary)">
                    {label}
                </Text>
                <Group gap={4} wrap="nowrap">
                    <span
                        className="instrument-value"
                        style={{ fontFamily: 'var(--font-mono, monospace)' }}
                    >
                        {value === null ? '--' : value.toFixed(1)}
                    </span>
                    <Text size="xs" c="dimmed">
                        {unit}
                    </Text>
                </Group>
            </Group>
            <Progress value={percentage} h={4} color={color} />
        </Stack>
    );
}
