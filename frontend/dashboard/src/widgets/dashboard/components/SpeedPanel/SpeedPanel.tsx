'use client';

import { Card, Stack, Text, Group } from '@mantine/core';
import type { TelemetryReading } from '@/features/telemetry/types';

interface SpeedPanelProps {
    speedActual: TelemetryReading | undefined;
    speedTarget: TelemetryReading | undefined;
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
    const rad = (angleDeg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
}

function describeArc(
    cx: number,
    cy: number,
    r: number,
    startAngle: number,
    endAngle: number,
): string {
    const start = polarToCartesian(cx, cy, r, startAngle);
    const end = polarToCartesian(cx, cy, r, endAngle);
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
}

function clamp(val: number, lo: number, hi: number) {
    return Math.min(hi, Math.max(lo, val));
}

const MAX_SPEED = 160;

export default function SpeedPanel({ speedActual, speedTarget }: SpeedPanelProps) {
    const actualValue = speedActual?.value ?? null;
    const targetValue = speedTarget?.value ?? null;

    const speedRatio = actualValue !== null ? clamp(actualValue / MAX_SPEED, 0, 1) : 0;
    const targetRatio = targetValue !== null ? clamp(targetValue / MAX_SPEED, 0, 1) : null;

    // Determine arc color based on difference between actual and target
    let arcColor = 'var(--mantine-color-healthy-5)';
    if (actualValue !== null && targetValue !== null) {
        const diff = Math.abs(actualValue - targetValue);
        if (diff >= 20) arcColor = 'var(--mantine-color-critical-5)';
        else if (diff >= 10) arcColor = 'var(--mantine-color-ktzGold-5)';
    }

    // Arc goes from 180° (left) to 0° (right), so foreground covers 180° to 180°-ratio*180°
    const fgEndAngle = 180 - speedRatio * 180;
    const bgPath = describeArc(100, 100, 80, 0, 180);
    const fgPath = speedRatio > 0 ? describeArc(100, 100, 80, fgEndAngle, 180) : '';

    // Target tick mark position
    let tickMark: { x1: number; y1: number; x2: number; y2: number } | null = null;
    if (targetRatio !== null) {
        const tickAngle = 180 - targetRatio * 180;
        const inner = polarToCartesian(100, 100, 70, tickAngle);
        const outer = polarToCartesian(100, 100, 90, tickAngle);
        tickMark = { x1: inner.x, y1: inner.y, x2: outer.x, y2: outer.y };
    }

    return (
        <Card
            padding="md"
            radius="md"
            style={{ borderTop: '2px solid var(--mantine-color-ktzBlue-5)' }}
        >
            <Stack gap="sm">
                <Text
                    size="xs"
                    fw={600}
                    c="var(--dashboard-text-secondary)"
                    style={{ letterSpacing: '0.05em', textTransform: 'uppercase' }}
                >
                    СКОРОСТЬ
                </Text>

                <svg
                    viewBox="0 0 200 120"
                    width="100%"
                    style={{ maxWidth: 240, alignSelf: 'center' }}
                >
                    {/* Background arc */}
                    <path
                        d={bgPath}
                        fill="none"
                        stroke="var(--mantine-color-dark-4)"
                        strokeWidth={10}
                        strokeLinecap="round"
                    />
                    {/* Foreground arc */}
                    {fgPath && (
                        <path
                            d={fgPath}
                            fill="none"
                            stroke={arcColor}
                            strokeWidth={10}
                            strokeLinecap="round"
                        />
                    )}
                    {/* Target tick */}
                    {tickMark && (
                        <line
                            x1={tickMark.x1}
                            y1={tickMark.y1}
                            x2={tickMark.x2}
                            y2={tickMark.y2}
                            stroke="var(--mantine-color-ktzGold-5)"
                            strokeWidth={3}
                            strokeLinecap="round"
                        />
                    )}
                </svg>

                <Group justify="center" align="baseline" gap={4}>
                    <span
                        className="instrument-value"
                        style={{
                            fontSize: 36,
                            fontFamily: 'var(--font-mono, monospace)',
                        }}
                    >
                        {actualValue !== null ? actualValue.toFixed(0) : '--'}
                    </span>
                    <Text size="sm" c="dimmed">
                        км/ч
                    </Text>
                </Group>

                <Text size="xs" c="var(--dashboard-text-secondary)" ta="center">
                    Целевая: {targetValue !== null ? `${targetValue.toFixed(0)} км/ч` : '-- км/ч'}
                </Text>
            </Stack>
        </Card>
    );
}
