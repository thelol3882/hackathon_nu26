'use client';

import { Group, Text, Progress, Stack, Tooltip } from '@mantine/core';

interface SensorRowProps {
    label: string;
    value: number | null;
    unit: string;
    min?: number;
    max?: number;
    warningMin?: number;
    warningMax?: number;
}

function getStatus(
    value: number | null,
    min: number,
    max: number,
    warningMin?: number,
    warningMax?: number,
): 'ok' | 'warning' | 'critical' | 'unknown' {
    if (value === null) return 'unknown';
    if (value < min || value > max) return 'critical';
    if (warningMin !== undefined && warningMax !== undefined) {
        if (value >= warningMin && value <= warningMax) return 'ok';
        return 'warning';
    }
    return 'ok';
}

const statusColors = {
    ok: 'var(--mantine-color-healthy-5)',
    warning: 'var(--mantine-color-ktzGold-5)',
    critical: 'var(--mantine-color-critical-5)',
    unknown: 'var(--mantine-color-gray-5)',
};

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
    const percentage = value === null ? 0 : clamp(((value - min) / (max - min)) * 100, 0, 100);
    const status = getStatus(value, min, max, warningMin, warningMax);
    const color = statusColors[status];
    const isCritical = status === 'critical';

    return (
        <Tooltip
            label={`${label}: ${value === null ? 'нет данных' : `${value.toFixed(2)} ${unit}`} (допуск: ${min}–${max} ${unit})`}
            position="top"
        >
            <Stack gap={3}>
                <Group justify="space-between" wrap="nowrap">
                    <Group gap={6} wrap="nowrap">
                        <div
                            style={{
                                width: 6,
                                height: 6,
                                borderRadius: '50%',
                                backgroundColor: color,
                                flexShrink: 0,
                                boxShadow: isCritical ? `0 0 6px ${color}` : undefined,
                                animation: isCritical
                                    ? 'pulse-led 1.5s ease-in-out infinite'
                                    : undefined,
                            }}
                        />
                        <Text size="xs" c="var(--dashboard-text-secondary)">
                            {label}
                        </Text>
                    </Group>
                    <Group gap={4} wrap="nowrap">
                        <span
                            className="instrument-value"
                            style={{
                                fontFamily: 'var(--font-mono, monospace)',
                                fontSize: 13,
                                fontWeight: isCritical ? 700 : 500,
                                color: isCritical ? color : undefined,
                            }}
                        >
                            {value === null ? '--' : value.toFixed(1)}
                        </span>
                        <Text size="xs" c="dimmed">
                            {unit}
                        </Text>
                    </Group>
                </Group>
                <Progress
                    value={percentage}
                    h={3}
                    color={color}
                    radius="xl"
                    style={{
                        transition: 'all 0.3s ease',
                    }}
                />
            </Stack>
        </Tooltip>
    );
}
