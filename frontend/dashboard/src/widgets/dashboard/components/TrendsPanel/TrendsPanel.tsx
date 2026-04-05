'use client';

import { useState, useMemo } from 'react';
import { Card, Text, Group, Select, SegmentedControl, Loader, Center, Badge } from '@mantine/core';
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
} from 'recharts';
import { useGetTelemetryQuery } from '@/features/telemetry';
import type { BucketInterval } from '@/features/telemetry';
import { minutesAgo, hoursAgo, dayjs } from '@/shared/utils/date';

interface TrendsPanelProps {
    locomotiveId: string | null;
    replayStart?: string;
    replayEnd?: string;
}

const sensorLabels: Record<string, string> = {
    speed_actual: 'Скорость',
    coolant_temp: 'Темп. охлаждения',
    oil_pressure: 'Давление масла',
    diesel_rpm: 'Обороты дизеля',
    fuel_level: 'Уровень топлива',
    fuel_rate: 'Расход топлива',
    brake_pipe_pressure: 'Давл. торм. маг.',
    traction_motor_temp: 'Темп. тяг. двиг.',
    crankcase_pressure: 'Давление картера',
    catenary_voltage: 'Напряжение сети',
    pantograph_current: 'Ток пантографа',
    transformer_temp: 'Темп. трансф.',
    igbt_temp: 'Темп. IGBT',
    dc_link_voltage: 'Напряжение DC',
    recuperation_current: 'Ток рекуперации',
};

const sensorOptions = Object.entries(sensorLabels).map(([value, label]) => ({ value, label }));

// Period = window size. Right edge = now, left edge = now - period.
const periodOptions = [
    { label: '5м', value: '5m' },
    { label: '15м', value: '15m' },
    { label: '30м', value: '30m' },
    { label: '1ч', value: '1h' },
    { label: '3ч', value: '3h' },
    { label: '6ч', value: '6h' },
    { label: '12ч', value: '12h' },
    { label: '24ч', value: '24h' },
];

const periodConfig: Record<
    string,
    { getStart: () => string; bucket_interval: BucketInterval; refreshMs: number }
> = {
    '5m': { getStart: () => minutesAgo(5), bucket_interval: '1 minute', refreshMs: 15_000 },
    '15m': { getStart: () => minutesAgo(15), bucket_interval: '1 minute', refreshMs: 15_000 },
    '30m': { getStart: () => minutesAgo(30), bucket_interval: '1 minute', refreshMs: 30_000 },
    '1h': { getStart: () => hoursAgo(1), bucket_interval: '5 minutes', refreshMs: 30_000 },
    '3h': { getStart: () => hoursAgo(3), bucket_interval: '10 minutes', refreshMs: 60_000 },
    '6h': { getStart: () => hoursAgo(6), bucket_interval: '15 minutes', refreshMs: 60_000 },
    '12h': { getStart: () => hoursAgo(12), bucket_interval: '30 minutes', refreshMs: 120_000 },
    '24h': { getStart: () => hoursAgo(24), bucket_interval: '1 hour', refreshMs: 120_000 },
};

function toEpoch(bucket: string | Date): number {
    return typeof bucket === 'string' ? new Date(bucket).getTime() : bucket.getTime();
}

function pickReplayBucket(startIso: string, endIso: string): BucketInterval {
    const diffMin = (new Date(endIso).getTime() - new Date(startIso).getTime()) / 60_000;
    if (diffMin <= 15) return '1 minute';
    if (diffMin <= 60) return '1 minute';
    if (diffMin <= 180) return '5 minutes';
    if (diffMin <= 720) return '15 minutes';
    return '1 hour';
}

/** X axis tick formatter — show date (05 апр) when day changes, else HH:mm */
function formatXTick(ts: number, index: number, allTicks: Array<{ value: number }>): string {
    const d = dayjs(ts);

    // Check if this is the first tick or the day changed
    if (index === 0) {
        return d.format('DD MMM');
    }

    // Find previous tick to check day boundary
    if (index > 0 && allTicks[index - 1]) {
        const prevDay = dayjs(allTicks[index - 1].value).format('DD');
        if (prevDay !== d.format('DD')) {
            return d.format('DD MMM');
        }
    }

    return d.format('HH:mm');
}

function CustomTooltipContent({
    active,
    payload,
    unit,
    sensorLabel,
}: {
    active?: boolean;
    payload?: Array<{
        value: number | null;
        payload: { min_value: number | null; max_value: number | null; ts: number };
    }>;
    unit: string;
    sensorLabel: string;
}) {
    if (!active || !payload?.length) return null;
    const d = payload[0];
    const avg = d.value;
    if (avg == null) return null;
    const ts = d.payload.ts;
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
                {dayjs(ts).format('DD.MM.YYYY HH:mm:ss')}
            </div>
            <div style={{ color: 'var(--dashboard-text-primary)' }}>
                {sensorLabel}: <strong>{avg.toFixed(2)}</strong> {unit}
            </div>
            {min != null && max != null && (
                <div style={{ color: 'var(--dashboard-text-secondary)', fontSize: 11 }}>
                    мин {min.toFixed(2)} / макс {max.toFixed(2)} {unit}
                </div>
            )}
        </div>
    );
}

export default function TrendsPanel({ locomotiveId, replayStart, replayEnd }: TrendsPanelProps) {
    const isReplay = !!(replayStart && replayEnd);
    const [selectedSensor, setSelectedSensor] = useState('speed_actual');
    const [selectedPeriod, setSelectedPeriod] = useState('15m');

    const cfg = periodConfig[selectedPeriod];

    // Query params
    const queryParams = useMemo(() => {
        if (isReplay) {
            return {
                locomotive_id: locomotiveId ?? undefined,
                sensor_type: selectedSensor,
                start: replayStart,
                end: replayEnd,
                bucket_interval: pickReplayBucket(replayStart!, replayEnd!),
                limit: 500,
            };
        }
        return {
            locomotive_id: locomotiveId ?? undefined,
            sensor_type: selectedSensor,
            start: cfg.getStart(),
            bucket_interval: cfg.bucket_interval,
            limit: 500,
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [locomotiveId, selectedSensor, selectedPeriod, isReplay, replayStart, replayEnd]);

    const { data, isFetching } = useGetTelemetryQuery(queryParams, {
        skip: !locomotiveId || (isReplay && (!replayStart || !replayEnd)),
        pollingInterval: isReplay ? 0 : cfg.refreshMs,
    });

    // Map to chart data
    const chartData = useMemo(() => {
        if (!data?.length) return [];
        return data
            .map((d) => ({
                ts: toEpoch(d.bucket),
                avg_value: d.avg_value,
                min_value: d.min_value,
                max_value: d.max_value,
                unit: d.unit,
            }))
            .filter((d) => d.avg_value != null);
    }, [data]);

    const unit = data?.find((d) => d.unit)?.unit ?? '';
    const sensorLabel = sensorLabels[selectedSensor] ?? selectedSensor;

    // Stats
    const stats = useMemo(() => {
        const values = chartData.map((d) => d.avg_value).filter((v): v is number => v != null);
        if (!values.length) return null;
        const avg = values.reduce((a, b) => a + b, 0) / values.length;
        return { avg, min: Math.min(...values), max: Math.max(...values) };
    }, [chartData]);

    // Custom tick formatter that knows about all ticks for day-boundary detection
    const tickFormatter = useMemo(() => {
        const ticks = chartData.map((d) => ({ value: d.ts }));
        return (ts: number, index: number) => formatXTick(ts, index, ticks);
    }, [chartData]);

    return (
        <Card
            style={{
                borderTop: `2px solid var(--mantine-color-${isReplay ? 'ktzGold' : 'ktzBlue'}-5)`,
            }}
        >
            <Group justify="space-between" mb="xs" wrap="wrap" gap="xs">
                <Group gap="xs">
                    <Text className="panel-label">ТРЕНДЫ</Text>
                    {isReplay && (
                        <Badge size="xs" variant="light" color="ktzGold">
                            REPLAY
                        </Badge>
                    )}
                    {isFetching && <Loader size={12} />}
                </Group>
                <Select
                    size="xs"
                    value={selectedSensor}
                    onChange={(v) => v && setSelectedSensor(v)}
                    data={sensorOptions}
                    w={180}
                    searchable
                    placeholder="Датчик"
                />
            </Group>

            {/* Period selector — only in live mode */}
            {!isReplay && (
                <SegmentedControl
                    size="xs"
                    value={selectedPeriod}
                    onChange={setSelectedPeriod}
                    data={periodOptions}
                    mb="sm"
                    fullWidth
                />
            )}

            {/* Stats */}
            {stats && (
                <Group gap="xs" mb="xs">
                    <Badge size="xs" variant="light" color="ktzBlue">
                        Сред: {stats.avg.toFixed(1)} {unit}
                    </Badge>
                    <Badge size="xs" variant="light" color="green">
                        Мин: {stats.min.toFixed(1)} {unit}
                    </Badge>
                    <Badge size="xs" variant="light" color="critical">
                        Макс: {stats.max.toFixed(1)} {unit}
                    </Badge>
                </Group>
            )}

            {/* Chart */}
            {!locomotiveId ? (
                <Center h={280}>
                    <Text c="dimmed">Выберите локомотив</Text>
                </Center>
            ) : isFetching && chartData.length === 0 ? (
                <Center h={280}>
                    <Loader size="sm" />
                </Center>
            ) : chartData.length === 0 ? (
                <Center h={280}>
                    <Text c="dimmed">Нет данных за выбранный период</Text>
                </Center>
            ) : (
                <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
                        <defs>
                            <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop
                                    offset="0%"
                                    stopColor={`var(--mantine-color-${isReplay ? 'ktzGold' : 'ktzBlue'}-5)`}
                                    stopOpacity={0.3}
                                />
                                <stop
                                    offset="100%"
                                    stopColor={`var(--mantine-color-${isReplay ? 'ktzGold' : 'ktzBlue'}-5)`}
                                    stopOpacity={0}
                                />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--dashboard-border)" />
                        <XAxis
                            dataKey="ts"
                            type="number"
                            scale="time"
                            domain={['dataMin', 'dataMax']}
                            tickFormatter={tickFormatter}
                            tick={{ fontSize: 11 }}
                            tickCount={8}
                        />
                        <YAxis
                            tick={{ fontSize: 11 }}
                            width={65}
                            domain={['auto', 'auto']}
                            tickFormatter={(v: number) => `${v}${unit ? ` ${unit}` : ''}`}
                        />
                        <Tooltip
                            content={<CustomTooltipContent unit={unit} sensorLabel={sensorLabel} />}
                        />
                        {stats && (
                            <ReferenceLine
                                y={stats.avg}
                                stroke="var(--mantine-color-ktzGold-5)"
                                strokeDasharray="5 5"
                                strokeOpacity={0.4}
                            />
                        )}
                        <Area
                            type="monotone"
                            dataKey="avg_value"
                            stroke={`var(--mantine-color-${isReplay ? 'ktzGold' : 'ktzBlue'}-5)`}
                            fill="url(#trendGrad)"
                            strokeWidth={2}
                            dot={false}
                            isAnimationActive={false}
                            connectNulls
                        />
                    </AreaChart>
                </ResponsiveContainer>
            )}
        </Card>
    );
}
