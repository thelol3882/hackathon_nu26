'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import {
    Card,
    Text,
    Group,
    Select,
    SegmentedControl,
    Loader,
    Center,
    ActionIcon,
    Tooltip as MantineTooltip,
} from '@mantine/core';
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Brush,
    ReferenceArea,
} from 'recharts';
import { useGetTelemetryQuery } from '@/features/telemetry';
import type { BucketInterval } from '@/features/telemetry';
import { minutesAgo, hoursAgo, formatTime } from '@/shared/utils/date';

interface TrendsPanelProps {
    locomotiveId: string | null;
}

const sensorLabels: Record<string, string> = {
    speed_actual: 'Скорость',
    coolant_temp: 'Темп. охлаждения',
    oil_pressure: 'Давление масла',
    diesel_rpm: 'Обороты дизеля',
    fuel_level: 'Уровень топлива',
    brake_pipe_pressure: 'Давл. тормозной магистрали',
};

const sensorOptions = Object.entries(sensorLabels).map(([value, label]) => ({
    value,
    label,
}));

const rangeOptions = [
    { label: '5м', value: '5m' },
    { label: '15м', value: '15m' },
    { label: '1ч', value: '1h' },
    { label: '24ч', value: '24h' },
];

const rangeConfig: Record<
    string,
    { getStart: () => string; bucket_interval: BucketInterval; tickCount: number }
> = {
    '5m': { getStart: () => minutesAgo(5), bucket_interval: '1 minute', tickCount: 5 },
    '15m': { getStart: () => minutesAgo(15), bucket_interval: '1 minute', tickCount: 8 },
    '1h': { getStart: () => hoursAgo(1), bucket_interval: '5 minutes', tickCount: 7 },
    '24h': { getStart: () => hoursAgo(24), bucket_interval: '1 hour', tickCount: 8 },
};

/** Convert bucket string to epoch ms for numeric axis */
function toEpoch(bucket: string): number {
    return new Date(bucket).getTime();
}

/** Format epoch ms to HH:mm */
function fmtTick(v: number): string {
    const d = new Date(v);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** Custom tooltip content */
function CustomTooltipContent({
    active,
    payload,
    label,
    unit,
    sensorLabel,
}: {
    active?: boolean;
    payload?: Array<{
        value: number | null;
        payload: { min_value: number | null; max_value: number | null };
    }>;
    label?: string;
    unit: string;
    sensorLabel: string;
}) {
    if (!active || !payload?.length) return null;
    const d = payload[0];
    const avg = d.value;
    if (avg == null) return null;
    const min = d.payload.min_value;
    const max = d.payload.max_value;

    return (
        <div
            style={{
                background: 'var(--dashboard-surface)',
                border: '1px solid var(--dashboard-border)',
                borderRadius: 8,
                padding: '8px 12px',
                fontSize: 12,
                lineHeight: 1.6,
                boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            }}
        >
            <div
                style={{
                    fontWeight: 600,
                    marginBottom: 2,
                    color: 'var(--dashboard-text-secondary)',
                }}
            >
                {formatTime(String(label))}
            </div>
            <div style={{ color: 'var(--dashboard-text-primary)' }}>
                {sensorLabel}: <strong>{avg.toFixed(1)}</strong> {unit}
            </div>
            {min != null && max != null && (
                <div style={{ color: 'var(--dashboard-text-secondary)', fontSize: 11 }}>
                    мин {min.toFixed(1)} / макс {max.toFixed(1)} {unit}
                </div>
            )}
        </div>
    );
}

export default function TrendsPanel({ locomotiveId }: TrendsPanelProps) {
    const [selectedSensor, setSelectedSensor] = useState('speed_actual');
    const [selectedRange, setSelectedRange] = useState('15m');
    const [pollTick, setPollTick] = useState(0);

    // Drag-to-zoom state
    const [zoomLeft, setZoomLeft] = useState<string | null>(null);
    const [zoomRight, setZoomRight] = useState<string | null>(null);
    const [zoomedDomain, setZoomedDomain] = useState<[number, number] | null>(null);

    // Increment tick every 30s so `start` recalculates (true sliding window)
    useEffect(() => {
        const id = setInterval(() => setPollTick((t) => t + 1), 30_000);
        return () => clearInterval(id);
    }, []);

    // Reset zoom when range or sensor changes
    useEffect(() => {
        setZoomedDomain(null);
    }, [selectedRange, selectedSensor, locomotiveId]);

    const queryParams = useMemo(() => {
        const cfg = rangeConfig[selectedRange];
        return {
            locomotive_id: locomotiveId ?? undefined,
            sensor_type: selectedSensor,
            start: cfg.getStart(),
            bucket_interval: cfg.bucket_interval,
            limit: 500,
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [locomotiveId, selectedSensor, selectedRange, pollTick]);

    const { data, isFetching } = useGetTelemetryQuery(queryParams, {
        skip: !locomotiveId,
        pollingInterval: 30000,
    });

    // Prepare chart data with epoch timestamps for numeric X axis
    const chartData = useMemo(() => {
        if (!data?.length) return [];
        return data.map((d) => ({ ...d, ts: toEpoch(d.bucket) }));
    }, [data]);

    const unit = data?.find((d) => d.unit)?.unit ?? '';
    const sensorLabel = sensorLabels[selectedSensor] ?? selectedSensor;
    const tickCount = rangeConfig[selectedRange].tickCount;

    // Drag-to-zoom handlers
    const handleMouseDown = useCallback(
        (e: { activeLabel?: string | number }) => {
            if (e?.activeLabel != null) setZoomLeft(String(e.activeLabel));
        },
        [],
    );

    const handleMouseMove = useCallback(
        (e: { activeLabel?: string | number }) => {
            if (zoomLeft && e?.activeLabel != null) setZoomRight(String(e.activeLabel));
        },
        [zoomLeft],
    );

    const handleMouseUp = useCallback(() => {
        if (zoomLeft && zoomRight) {
            const left = Number(zoomLeft);
            const right = Number(zoomRight);
            if (left !== right) {
                setZoomedDomain([Math.min(left, right), Math.max(left, right)]);
            }
        }
        setZoomLeft(null);
        setZoomRight(null);
    }, [zoomLeft, zoomRight]);

    const resetZoom = useCallback(() => setZoomedDomain(null), []);

    // X axis domain
    const xDomain = useMemo<[number, number] | undefined>(() => {
        if (zoomedDomain) return zoomedDomain;
        if (!chartData.length) return undefined;
        return [chartData[0].ts, chartData[chartData.length - 1].ts];
    }, [chartData, zoomedDomain]);

    return (
        <Card style={{ borderTop: '2px solid var(--mantine-color-ktzBlue-5)' }}>
            <Group justify="space-between" mb="sm" wrap="wrap" gap="xs">
                <Group gap="xs">
                    <Text className="panel-label">ТРЕНДЫ</Text>
                    {zoomedDomain && (
                        <MantineTooltip label="Сбросить зум">
                            <ActionIcon
                                variant="subtle"
                                size="xs"
                                onClick={resetZoom}
                                color="ktzBlue"
                            >
                                ↻
                            </ActionIcon>
                        </MantineTooltip>
                    )}
                </Group>
                <Group gap="xs" wrap="wrap">
                    <Select
                        size="xs"
                        value={selectedSensor}
                        onChange={(v) => v && setSelectedSensor(v)}
                        data={sensorOptions}
                        w={180}
                    />
                    <SegmentedControl
                        size="xs"
                        value={selectedRange}
                        onChange={setSelectedRange}
                        data={rangeOptions}
                    />
                </Group>
            </Group>

            {!locomotiveId ? (
                <Center h={280}>
                    <Text c="dimmed">Выберите локомотив</Text>
                </Center>
            ) : isFetching && !data ? (
                <Center h={280}>
                    <Loader size="sm" />
                </Center>
            ) : !data || data.length === 0 ? (
                <Center h={280}>
                    <Text c="dimmed">Нет данных</Text>
                </Center>
            ) : (
                <ResponsiveContainer width="100%" height={320}>
                    <AreaChart
                        data={chartData}
                        onMouseDown={handleMouseDown}
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                    >
                        <defs>
                            <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop
                                    offset="0%"
                                    stopColor="var(--mantine-color-ktzBlue-5)"
                                    stopOpacity={0.3}
                                />
                                <stop
                                    offset="100%"
                                    stopColor="var(--mantine-color-ktzBlue-5)"
                                    stopOpacity={0}
                                />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--dashboard-border)" />
                        <XAxis
                            dataKey="ts"
                            type="number"
                            scale="time"
                            domain={xDomain}
                            tickCount={tickCount}
                            tickFormatter={fmtTick}
                            tick={{ fontSize: 11 }}
                        />
                        <YAxis
                            tick={{ fontSize: 11 }}
                            width={70}
                            domain={[0, 'auto']}
                            allowDecimals={false}
                            tickFormatter={(v: number) =>
                                `${v}${unit ? ` ${unit}` : ''}`
                            }
                        />
                        <Tooltip
                            content={
                                <CustomTooltipContent unit={unit} sensorLabel={sensorLabel} />
                            }
                        />
                        <Area
                            type="monotone"
                            dataKey="avg_value"
                            stroke="var(--mantine-color-ktzBlue-5)"
                            fill="url(#trendGradient)"
                            strokeWidth={2}
                            dot={false}
                            isAnimationActive={false}
                            connectNulls
                        />
                        {/* Drag-to-zoom selection overlay */}
                        {zoomLeft && zoomRight && (
                            <ReferenceArea
                                x1={Number(zoomLeft)}
                                x2={Number(zoomRight)}
                                strokeOpacity={0.3}
                                fill="var(--mantine-color-ktzBlue-2)"
                                fillOpacity={0.3}
                            />
                        )}
                        {/* Brush for fine-grained scroll/zoom at bottom */}
                        <Brush
                            dataKey="ts"
                            height={28}
                            stroke="var(--mantine-color-ktzBlue-5)"
                            fill="var(--dashboard-surface)"
                            tickFormatter={fmtTick}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            )}
        </Card>
    );
}
