'use client';

/**
 * TrendsPanel — DigitalOcean-style real-time line chart over a single sensor.
 *
 * Architecture:
 *   • The chart itself is rendered by uPlot (canvas) via UPlotChart.tsx, so we
 *     can comfortably push 1000+ points without dropping frames.
 *   • The backend does the heavy lifting via LTTB downsampling: we ask for
 *     `max_points ≈ container width` and it returns a series whose visual
 *     shape matches the raw data (peaks/valleys preserved) but fits the
 *     pixel grid.
 *   • Real outages are encoded server-side as `is_gap` markers (the value
 *     fields are zeroed). uPlot natively breaks the line on null/NaN, so
 *     missing data shows as a gap, not as a fake plateau.
 *   • The visible time window slides forward on a `nowTick` timer so the
 *     right edge always anchors to "now", same as DO's monitoring page.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    ActionIcon,
    Badge,
    Card,
    Center,
    Group,
    Loader,
    Select,
    Text,
    Tooltip as MantineTooltip,
} from '@mantine/core';
import dynamic from 'next/dynamic';
import { useGetTelemetryQuery } from '@/features/telemetry';
import type { BucketInterval } from '@/features/telemetry';
import { dayjs, hoursAgo, minutesAgo } from '@/shared/utils/date';

// uPlot is canvas-only and reaches into `document` on construction, so it
// must run client-side. `dynamic` keeps it out of the SSR bundle.
const UPlotChart = dynamic(() => import('./UPlotChart'), { ssr: false });

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

const sensorOptions = Object.entries(sensorLabels).map(([value, label]) => ({
    value,
    label,
}));

const periodOptions = [
    { label: '5 минут', value: '5m' },
    { label: '15 минут', value: '15m' },
    { label: '30 минут', value: '30m' },
    { label: '1 час', value: '1h' },
    { label: '3 часа', value: '3h' },
    { label: '6 часов', value: '6h' },
    { label: '12 часов', value: '12h' },
    { label: '24 часа', value: '24h' },
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

/**
 * Pick a server-side bucket size proportional to the visible window. These
 * values are the *raw* aggregation grid; the LTTB pass on the backend then
 * compresses them to ~`max_points` while preserving spikes. So a 6h window
 * with 20 s buckets = 1080 raw points → ~chart-width sampled points.
 */
function autoBucket(durationMs: number): BucketInterval {
    const min = durationMs / 60_000;
    if (min <= 5) return '2 seconds';
    if (min <= 15) return '5 seconds';
    if (min <= 30) return '10 seconds';
    if (min <= 60) return '15 seconds';
    if (min <= 180) return '20 seconds';
    if (min <= 360) return '20 seconds';
    if (min <= 720) return '40 seconds';
    return '1 minute';
}

function toEpochMs(bucket: string | Date): number {
    return typeof bucket === 'string' ? new Date(bucket).getTime() : bucket.getTime();
}

interface ChartSeries {
    timestamps: number[]; // epoch SECONDS (uPlot convention)
    values: Array<number | null>;
    minValues: Array<number | null>;
    maxValues: Array<number | null>;
}

const EMPTY_SERIES: ChartSeries = {
    timestamps: [],
    values: [],
    minValues: [],
    maxValues: [],
};

export default function TrendsPanel({
    locomotiveId,
    replayStart,
    replayEnd,
}: TrendsPanelProps) {
    const isReplay = !!(replayStart && replayEnd);
    const [selectedSensor, setSelectedSensor] = useState('speed_actual');
    const [selectedPeriod, setSelectedPeriod] = useState('15m');

    const [zoomStack, setZoomStack] = useState<Array<{ start: string; end: string }>>([]);

    const cfg = periodConfig[selectedPeriod];
    const isZoomed = zoomStack.length > 0;

    // Sliding-window tick. The right edge of the chart should always read
    // "now" (DO-style), so we recompute currentWindow on the same cadence
    // we poll the API at.
    const [nowTick, setNowTick] = useState(() => Date.now());
    useEffect(() => {
        if (isReplay || isZoomed) return;
        const id = setInterval(() => setNowTick(Date.now()), cfg.refreshMs);
        return () => clearInterval(id);
    }, [isReplay, isZoomed, cfg.refreshMs]);

    const currentWindow = useMemo(() => {
        if (isZoomed) {
            const top = zoomStack[zoomStack.length - 1];
            return { start: top.start, end: top.end };
        }
        if (isReplay) {
            return { start: replayStart!, end: replayEnd! };
        }
        return { start: cfg.getStart(), end: new Date().toISOString() };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isReplay, replayStart, replayEnd, isZoomed, zoomStack, selectedPeriod, nowTick]);

    const startMs = new Date(currentWindow.start).getTime();
    const endMs = new Date(currentWindow.end).getTime();
    const windowDurationMs = endMs - startMs;
    const bucket = autoBucket(windowDurationMs);

    // Container width drives `max_points`: we don't ask for more points
    // than the chart can actually display. Initially we don't know the
    // width, so we start with a sensible default and refine on first paint.
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [chartWidth, setChartWidth] = useState(900);
    useEffect(() => {
        if (!containerRef.current) return;
        const ro = new ResizeObserver((entries) => {
            const w = Math.round(entries[0]?.contentRect.width ?? 900);
            if (w > 0) setChartWidth(w);
        });
        ro.observe(containerRef.current);
        return () => ro.disconnect();
    }, []);

    // We round max_points to the nearest 100 so width-jitter doesn't
    // invalidate the RTK Query cache key on every pixel.
    const maxPoints = Math.max(200, Math.round(chartWidth / 100) * 100);

    const queryParams = useMemo(
        () => ({
            locomotive_id: locomotiveId ?? undefined,
            sensor_type: selectedSensor,
            start: currentWindow.start,
            end: currentWindow.end,
            bucket_interval: bucket,
            max_points: maxPoints,
            limit: 5000,
        }),
        [locomotiveId, selectedSensor, currentWindow, bucket, maxPoints],
    );

    const { data, isFetching } = useGetTelemetryQuery(queryParams, {
        skip: !locomotiveId || (isReplay && (!replayStart || !replayEnd)),
        pollingInterval: isReplay || isZoomed ? 0 : cfg.refreshMs,
    });

    // Convert the wire format (ISO string buckets, gap markers) into the
    // parallel arrays uPlot expects. Timestamps are in seconds.
    const series: ChartSeries = useMemo(() => {
        if (!data?.length) return EMPTY_SERIES;
        const ts: number[] = [];
        const vs: Array<number | null> = [];
        const mins: Array<number | null> = [];
        const maxs: Array<number | null> = [];
        for (const b of data) {
            ts.push(toEpochMs(b.bucket) / 1000);
            if (b.is_gap || b.avg_value == null) {
                vs.push(null);
                mins.push(null);
                maxs.push(null);
            } else {
                vs.push(b.avg_value);
                mins.push(b.min_value);
                maxs.push(b.max_value);
            }
        }
        return { timestamps: ts, values: vs, minValues: mins, maxValues: maxs };
    }, [data]);

    const stats = useMemo(() => {
        const real = series.values.filter((v): v is number => v != null);
        if (!real.length) return null;
        const sum = real.reduce((a, b) => a + b, 0);
        return {
            avg: sum / real.length,
            min: Math.min(...real),
            max: Math.max(...real),
        };
    }, [series]);

    const unit = data?.find((d) => d.unit)?.unit ?? '';
    const sensorLabel = sensorLabels[selectedSensor] ?? selectedSensor;

    const handleResetZoom = useCallback(() => setZoomStack([]), []);
    const handleZoomBack = useCallback(
        () => setZoomStack((prev) => prev.slice(0, -1)),
        [],
    );
    const handlePeriodChange = useCallback((v: string) => {
        setSelectedPeriod(v);
        setZoomStack([]);
    }, []);

    // uPlot reports the zoom selection in epoch SECONDS — convert back
    // to ISO strings for the URL/cache key.
    const handleZoomSelect = useCallback((leftSec: number, rightSec: number) => {
        const left = Math.round(leftSec * 1000);
        const right = Math.round(rightSec * 1000);
        if (right - left < 5_000) return; // ignore micro-drags
        setZoomStack((prev) => [
            ...prev,
            {
                start: new Date(left).toISOString(),
                end: new Date(right).toISOString(),
            },
        ]);
    }, []);

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

    const accentColor = isReplay
        ? 'var(--mantine-color-ktzGold-5)'
        : 'var(--mantine-color-ktzBlue-5)';

    const yTickFormatter = useCallback(
        (v: number) => {
            // Trim trailing zeros for compactness; never show more than 2 dp.
            const rounded = Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1);
            return unit ? `${rounded} ${unit}` : rounded;
        },
        [unit],
    );

    const hasAnyValue = series.values.some((v) => v != null);

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

            {!isReplay && (
                <Select
                    size="xs"
                    label="Период"
                    value={selectedPeriod}
                    onChange={(v) => v && handlePeriodChange(v)}
                    data={periodOptions}
                    allowDeselect={false}
                    w={180}
                    mb="sm"
                />
            )}

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

            {!locomotiveId ? (
                <Center h={300}>
                    <Text c="dimmed">Выберите локомотив</Text>
                </Center>
            ) : isFetching && data === undefined ? (
                <Center h={300}>
                    <Loader size="sm" />
                </Center>
            ) : (
                <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
                    {!hasAnyValue && (
                        <div
                            style={{
                                position: 'absolute',
                                inset: 0,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                pointerEvents: 'none',
                                zIndex: 2,
                            }}
                        >
                            <Text c="dimmed" size="sm">
                                Нет данных за выбранный период
                            </Text>
                        </div>
                    )}
                    <UPlotChart
                        timestamps={series.timestamps}
                        values={series.values}
                        minValues={series.minValues}
                        maxValues={series.maxValues}
                        xMin={Math.round(startMs / 1000)}
                        xMax={Math.round(endMs / 1000)}
                        color={accentColor}
                        sensorLabel={sensorLabel}
                        unit={unit}
                        yTickFormatter={yTickFormatter}
                        onZoomSelect={handleZoomSelect}
                        height={300}
                    />
                </div>
            )}
        </Card>
    );
}
