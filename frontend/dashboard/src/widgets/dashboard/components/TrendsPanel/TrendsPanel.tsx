'use client';

import { useState, useMemo, useCallback } from 'react';
import {
    Card,
    Text,
    Group,
    Select,
    SegmentedControl,
    Loader,
    Center,
    Badge,
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
    ReferenceLine,
    ReferenceArea,
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

const periodConfig: Record<string, { getStart: () => string; refreshMs: number }> = {
    '5m': { getStart: () => minutesAgo(5), refreshMs: 15_000 },
    '15m': { getStart: () => minutesAgo(15), refreshMs: 15_000 },
    '30m': { getStart: () => minutesAgo(30), refreshMs: 30_000 },
    '1h': { getStart: () => hoursAgo(1), refreshMs: 30_000 },
    '3h': { getStart: () => hoursAgo(3), refreshMs: 60_000 },
    '6h': { getStart: () => hoursAgo(6), refreshMs: 60_000 },
    '12h': { getStart: () => hoursAgo(12), refreshMs: 120_000 },
    '24h': { getStart: () => hoursAgo(24), refreshMs: 120_000 },
};

/** Auto-pick bucket interval based on window duration in ms */
function autoBucket(durationMs: number): BucketInterval {
    const min = durationMs / 60_000;
    if (min <= 5) return '1 minute';
    if (min <= 30) return '1 minute';
    if (min <= 90) return '5 minutes';
    if (min <= 360) return '10 minutes';
    if (min <= 720) return '15 minutes';
    if (min <= 1440) return '30 minutes';
    return '1 hour';
}

function toEpoch(bucket: string | Date): number {
    return typeof bucket === 'string' ? new Date(bucket).getTime() : bucket.getTime();
}

/** Format X tick — show "DD MMM" only when day changes from previous tick, else HH:mm */
function formatXTick(ts: number, index: number, allTicks: Array<{ value: number }>): string {
    const d = dayjs(ts);
    // Only show date when the day differs from the previous tick (midnight crossing)
    if (index > 0 && allTicks[index - 1]) {
        const prevDay = dayjs(allTicks[index - 1].value).format('DD');
        if (prevDay !== d.format('DD')) return d.format('DD MMM');
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
    const { ts, min_value: min, max_value: max } = d.payload;
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

    // Zoom stack: each entry = { start, end } ISO strings. Empty = no zoom.
    const [zoomStack, setZoomStack] = useState<Array<{ start: string; end: string }>>([]);

    // Drag selection state
    const [dragStart, setDragStart] = useState<number | null>(null);
    const [dragEnd, setDragEnd] = useState<number | null>(null);

    const cfg = periodConfig[selectedPeriod];
    const isZoomed = zoomStack.length > 0;

    // Current window: zoom overrides period
    const currentWindow = useMemo(() => {
        // Zoom always takes priority (works in both live and replay)
        if (isZoomed) {
            const top = zoomStack[zoomStack.length - 1];
            return { start: top.start, end: top.end };
        }
        if (isReplay) {
            return { start: replayStart!, end: replayEnd! };
        }
        return { start: cfg.getStart(), end: new Date().toISOString() };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isReplay, replayStart, replayEnd, isZoomed, zoomStack, selectedPeriod]);

    const windowDurationMs =
        new Date(currentWindow.end).getTime() - new Date(currentWindow.start).getTime();
    const bucket = autoBucket(windowDurationMs);

    // Query
    const queryParams = useMemo(
        () => ({
            locomotive_id: locomotiveId ?? undefined,
            sensor_type: selectedSensor,
            start: currentWindow.start,
            end: currentWindow.end,
            bucket_interval: bucket,
            limit: 500,
        }),
        [locomotiveId, selectedSensor, currentWindow, bucket],
    );

    const { data, isFetching } = useGetTelemetryQuery(queryParams, {
        skip: !locomotiveId || (isReplay && (!replayStart || !replayEnd)),
        pollingInterval: isReplay || isZoomed ? 0 : cfg.refreshMs,
    });

    // Chart data
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

    // X tick formatter with day boundary detection
    const tickFormatter = useMemo(() => {
        const ticks = chartData.map((d) => ({ value: d.ts }));
        return (ts: number, index: number) => formatXTick(ts, index, ticks);
    }, [chartData]);

    // Drag-to-zoom handlers
    const handleMouseDown = useCallback((e: { activeLabel?: string | number }) => {
        if (e?.activeLabel != null) setDragStart(Number(e.activeLabel));
    }, []);

    const handleMouseMove = useCallback(
        (e: { activeLabel?: string | number }) => {
            if (dragStart != null && e?.activeLabel != null) setDragEnd(Number(e.activeLabel));
        },
        [dragStart],
    );

    const handleMouseUp = useCallback(() => {
        if (dragStart != null && dragEnd != null && dragStart !== dragEnd) {
            const left = Math.min(dragStart, dragEnd);
            const right = Math.max(dragStart, dragEnd);
            // Only zoom if selection is at least 10 seconds
            if (right - left > 10_000) {
                setZoomStack((prev) => [
                    ...prev,
                    { start: new Date(left).toISOString(), end: new Date(right).toISOString() },
                ]);
            }
        }
        setDragStart(null);
        setDragEnd(null);
    }, [dragStart, dragEnd]);

    const handleResetZoom = useCallback(() => {
        setZoomStack([]);
    }, []);

    const handleZoomBack = useCallback(() => {
        setZoomStack((prev) => prev.slice(0, -1));
    }, []);

    // Reset zoom when period or sensor changes
    const handlePeriodChange = useCallback((v: string) => {
        setSelectedPeriod(v);
        setZoomStack([]);
    }, []);

    // Window label for zoomed state
    const windowLabel = useMemo(() => {
        if (!isZoomed) return null;
        const s = dayjs(currentWindow.start).format('HH:mm:ss');
        const e = dayjs(currentWindow.end).format('HH:mm:ss');
        const dur = Math.round(windowDurationMs / 1000);
        const durLabel =
            dur >= 3600
                ? `${(dur / 3600).toFixed(1)}ч`
                : dur >= 60
                  ? `${Math.round(dur / 60)}м`
                  : `${dur}с`;
        return `${s} — ${e} (${durLabel})`;
    }, [isZoomed, currentWindow, windowDurationMs]);

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
                    {isZoomed && (
                        <>
                            <Badge size="xs" variant="filled" color="ktzCyan">
                                ZOOM x{zoomStack.length}
                            </Badge>
                            <MantineTooltip label="Сбросить зум">
                                <ActionIcon
                                    variant="subtle"
                                    size="xs"
                                    onClick={handleResetZoom}
                                    color="ktzCyan"
                                >
                                    ↻
                                </ActionIcon>
                            </MantineTooltip>
                            {zoomStack.length > 1 && (
                                <MantineTooltip label="Назад">
                                    <ActionIcon
                                        variant="subtle"
                                        size="xs"
                                        onClick={handleZoomBack}
                                        color="gray"
                                    >
                                        ←
                                    </ActionIcon>
                                </MantineTooltip>
                            )}
                        </>
                    )}
                    {isFetching && <Loader size={12} />}
                </Group>
                <Select
                    size="xs"
                    value={selectedSensor}
                    onChange={(v) => {
                        if (v) {
                            setSelectedSensor(v);
                            setZoomStack([]);
                        }
                    }}
                    data={sensorOptions}
                    w={180}
                    searchable
                    placeholder="Датчик"
                />
            </Group>

            {/* Period selector */}
            {!isReplay && (
                <SegmentedControl
                    size="xs"
                    value={selectedPeriod}
                    onChange={handlePeriodChange}
                    data={periodOptions}
                    mb="sm"
                    fullWidth
                />
            )}

            {/* Zoom window info */}
            {isZoomed && windowLabel && (
                <Group gap="xs" mb="xs">
                    <Badge
                        size="xs"
                        variant="outline"
                        color="ktzCyan"
                        ff="var(--font-mono), monospace"
                    >
                        {windowLabel}
                    </Badge>
                    <Badge size="xs" variant="outline" color="gray">
                        шаг: {bucket}
                    </Badge>
                </Group>
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
                    <AreaChart
                        data={chartData}
                        margin={{ top: 5, right: 10, bottom: 5, left: 0 }}
                        onMouseDown={handleMouseDown}
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                        style={{ cursor: 'crosshair' }}
                    >
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
                        {/* Drag selection overlay */}
                        {dragStart != null && dragEnd != null && (
                            <ReferenceArea
                                x1={Math.min(dragStart, dragEnd)}
                                x2={Math.max(dragStart, dragEnd)}
                                fill="var(--mantine-color-ktzCyan-5)"
                                fillOpacity={0.15}
                                stroke="var(--mantine-color-ktzCyan-5)"
                                strokeOpacity={0.4}
                            />
                        )}
                    </AreaChart>
                </ResponsiveContainer>
            )}
        </Card>
    );
}
