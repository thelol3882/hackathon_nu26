'use client';

import { useState, useMemo, useCallback, useEffect } from 'react';
import {
    Card,
    Text,
    Group,
    Select,
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
    { label: '5 minutes', value: '5m' },
    { label: '15 minutes', value: '15m' },
    { label: '30 minutes', value: '30m' },
    { label: '1 hour', value: '1h' },
    { label: '3 hours', value: '3h' },
    { label: '6 hours', value: '6h' },
    { label: '12 hours', value: '12h' },
    { label: '24 hours', value: '24h' },
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
 * Pick a bucket size small enough that the line feels smooth but large enough
 * to keep the number of points bounded. The values mirror the DigitalOcean
 * monitoring charts the user referenced — e.g. ~15 s for a 1 hour window,
 * ~20 s for 6 hours.
 */
function autoBucket(durationMs: number): BucketInterval {
    const min = durationMs / 60_000;
    if (min <= 5) return '2 seconds'; // 150 pts
    if (min <= 15) return '5 seconds'; // 180 pts
    if (min <= 30) return '10 seconds'; // 180 pts
    if (min <= 60) return '15 seconds'; // 240 pts — 1 h
    if (min <= 180) return '20 seconds'; // 540 pts — 3 h
    if (min <= 360) return '20 seconds'; // 1080 pts — 6 h (per user spec)
    if (min <= 720) return '40 seconds'; // 1080 pts — 12 h
    return '1 minute'; // 1440 pts — 24 h
}

function toEpoch(bucket: string | Date): number {
    return typeof bucket === 'string' ? new Date(bucket).getTime() : bucket.getTime();
}

/** Size of one aggregation bucket in milliseconds. */
function bucketMs(b: BucketInterval): number {
    switch (b) {
        case '2 seconds':
            return 2_000;
        case '5 seconds':
            return 5_000;
        case '10 seconds':
            return 10_000;
        case '15 seconds':
            return 15_000;
        case '20 seconds':
            return 20_000;
        case '30 seconds':
            return 30_000;
        case '40 seconds':
            return 40_000;
        case '1 minute':
            return 60_000;
        case '5 minutes':
            return 5 * 60_000;
        case '10 minutes':
            return 10 * 60_000;
        case '15 minutes':
            return 15 * 60_000;
        case '30 minutes':
            return 30 * 60_000;
        case '1 hour':
            return 60 * 60_000;
        case '1 day':
            return 24 * 60 * 60_000;
        default:
            return 60_000;
    }
}

/**
 * DigitalOcean-style "nice" X-axis tick step. Picks a round duration for label
 * spacing (e.g. 5 min for a 1 h window, 30 min for 6 h) so the ticks land on
 * human-friendly boundaries (16:05, 16:10, …) regardless of where the window
 * actually starts.
 */
function niceTickStepMs(windowDurationMs: number): number {
    const s = 1000;
    const m = 60 * s;
    const h = 60 * m;
    if (windowDurationMs <= 5 * m) return 30 * s;
    if (windowDurationMs <= 15 * m) return 2 * m;
    if (windowDurationMs <= 30 * m) return 5 * m;
    if (windowDurationMs <= 60 * m) return 5 * m; // 1 h → every 5 min
    if (windowDurationMs <= 3 * h) return 15 * m;
    if (windowDurationMs <= 6 * h) return 30 * m; // 6 h → every 30 min
    if (windowDurationMs <= 12 * h) return 1 * h;
    return 2 * h; // 24 h → every 2 h
}

/**
 * Build explicit X-axis ticks spanning the FULL time window (not just the data
 * extent). This makes the chart behave like DigitalOcean's metrics: the right
 * edge always anchors to "now" (or window end), the left edge to window start,
 * and missing data simply leaves an empty area instead of compressing the axis.
 *
 * Ticks are placed on round, human-friendly boundaries (16:05, 16:10, …) at a
 * step chosen by `niceTickStepMs` based on the visible window length. The
 * label format auto-adapts: HH:mm:ss when the tick step is below 1 minute,
 * HH:mm otherwise; days are added on midnight crossings.
 */
function buildXAxis(
    startMs: number,
    endMs: number,
): { ticks: number[]; formatter: (ts: number, index: number) => string } {
    const windowDurationMs = endMs - startMs;
    const baseFmt = windowDurationMs < 10 * 60_000 ? 'HH:mm:ss' : 'HH:mm';

    if (windowDurationMs <= 0) {
        return { ticks: [], formatter: (ts) => dayjs(ts).format(baseFmt) };
    }

    const step = niceTickStepMs(windowDurationMs);

    // Snap first tick up to the next multiple of `step` aligned to the LOCAL
    // timezone, not to UTC — otherwise ticks could land at 16:02 instead of
    // the expected 16:05 for users not in UTC.
    const tzOffsetMs = new Date(startMs).getTimezoneOffset() * 60_000;
    const firstTick = Math.ceil((startMs - tzOffsetMs) / step) * step + tzOffsetMs;

    const picked: number[] = [];
    const seen = new Set<string>();
    for (let t = firstTick; t <= endMs; t += step) {
        const label = dayjs(t).format(baseFmt);
        if (!seen.has(label)) {
            seen.add(label);
            picked.push(t);
        }
        // Hard safety cap — should never trigger for normal windows.
        if (picked.length > 64) break;
    }

    const formatter = (ts: number, index: number) => {
        const d = dayjs(ts);
        if (index > 0 && picked[index - 1] != null) {
            const prevDay = dayjs(picked[index - 1]).format('DD');
            if (prevDay !== d.format('DD')) return d.format('DD MMM');
        }
        return d.format(baseFmt);
    };

    return { ticks: picked, formatter };
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

    const [zoomStack, setZoomStack] = useState<Array<{ start: string; end: string }>>([]);

    const [dragStart, setDragStart] = useState<number | null>(null);
    const [dragEnd, setDragEnd] = useState<number | null>(null);

    const cfg = periodConfig[selectedPeriod];
    const isZoomed = zoomStack.length > 0;

    // Tick used to slide the live window so the right edge always anchors to
    // "now" (Digital Ocean-style), instead of being frozen at mount time.
    // Disabled while replaying or zoomed (those windows are absolute).
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
    const stepMs = bucketMs(bucket);

    const queryParams = useMemo(
        () => ({
            locomotive_id: locomotiveId ?? undefined,
            sensor_type: selectedSensor,
            start: currentWindow.start,
            end: currentWindow.end,
            bucket_interval: bucket,
            // High-resolution buckets (e.g. 20 s for 6 h = 1080 pts) need
            // enough headroom beyond the default 500.
            limit: 2000,
        }),
        [locomotiveId, selectedSensor, currentWindow, bucket],
    );

    const { data, isFetching } = useGetTelemetryQuery(queryParams, {
        skip: !locomotiveId || (isReplay && (!replayStart || !replayEnd)),
        pollingInterval: isReplay || isZoomed ? 0 : cfg.refreshMs,
    });

    /**
     * Build a fully-populated, evenly-spaced series spanning [startMs, endMs].
     * Real backend buckets are placed at their timestamps; missing slots are
     * filled with `null` so the line chart shows an explicit gap (no point) for
     * intervals when the backend was offline / had no telemetry, instead of
     * connecting across the dead zone or compressing the axis.
     */
    const chartData = useMemo(() => {
        if (windowDurationMs <= 0 || stepMs <= 0) return [];

        type Point = {
            ts: number;
            avg_value: number | null;
            min_value: number | null;
            max_value: number | null;
            unit: string;
        };

        const byBucket = new Map<number, Point>();
        (data ?? []).forEach((d) => {
            // Snap each backend bucket to the local grid so map lookups work
            // even if there are sub-millisecond differences.
            const ts = Math.round(toEpoch(d.bucket) / stepMs) * stepMs;
            byBucket.set(ts, {
                ts,
                avg_value: d.avg_value,
                min_value: d.min_value,
                max_value: d.max_value,
                unit: d.unit ?? '',
            });
        });

        const firstBucket = Math.ceil(startMs / stepMs) * stepMs;
        const lastBucket = Math.floor(endMs / stepMs) * stepMs;
        const result: Point[] = [];
        for (let t = firstBucket; t <= lastBucket; t += stepMs) {
            const existing = byBucket.get(t);
            result.push(
                existing ?? {
                    ts: t,
                    avg_value: null,
                    min_value: null,
                    max_value: null,
                    unit: '',
                },
            );
        }
        return result;
    }, [data, startMs, endMs, stepMs, windowDurationMs]);

    const unit = data?.find((d) => d.unit)?.unit ?? '';
    const sensorLabel = sensorLabels[selectedSensor] ?? selectedSensor;

    const stats = useMemo(() => {
        const values = chartData.map((d) => d.avg_value).filter((v): v is number => v != null);
        if (!values.length) return null;
        const avg = values.reduce((a, b) => a + b, 0) / values.length;
        return { avg, min: Math.min(...values), max: Math.max(...values) };
    }, [chartData]);

    const { ticks: xTicks, formatter: tickFormatter } = useMemo(
        () => buildXAxis(startMs, endMs),
        [startMs, endMs],
    );

    const hasAnyValue = useMemo(
        () => chartData.some((d) => d.avg_value != null),
        [chartData],
    );

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

    const handlePeriodChange = useCallback((v: string) => {
        setSelectedPeriod(v);
        setZoomStack([]);
    }, []);

    /**
     * Render a dot only for data points that are "isolated" — i.e. both the
     * previous and next bucket are null. Without this a single surviving data
     * point (e.g. the first reading after a backend restart) would be invisible
     * because `<Area>` cannot draw a line of zero length.
     * Continuous stretches still render without dots for a clean look.
     */
    const dotColor = `var(--mantine-color-${isReplay ? 'ktzGold' : 'ktzBlue'}-5)`;
    const renderIsolatedDot = useCallback(
        (props: {
            cx?: number;
            cy?: number;
            index?: number;
            value?: number | null;
        }) => {
            const { cx, cy, index, value } = props;
            if (
                value == null ||
                cx == null ||
                cy == null ||
                index == null ||
                !Number.isFinite(cx) ||
                !Number.isFinite(cy)
            ) {
                return <g />;
            }
            const prev = chartData[index - 1]?.avg_value;
            const next = chartData[index + 1]?.avg_value;
            if (prev == null && next == null) {
                return (
                    <circle
                        cx={cx}
                        cy={cy}
                        r={3}
                        fill={dotColor}
                        stroke={dotColor}
                        strokeWidth={1}
                    />
                );
            }
            return <g />;
        },
        [chartData, dotColor],
    );

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

            {!isReplay && (
                <Select
                    size="xs"
                    label="Select period"
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
                <Center h={280}>
                    <Text c="dimmed">Выберите локомотив</Text>
                </Center>
            ) : isFetching && data === undefined ? (
                <Center h={280}>
                    <Loader size="sm" />
                </Center>
            ) : (
                <div style={{ position: 'relative', width: '100%', height: 300 }}>
                    {!hasAnyValue && (
                        <div
                            style={{
                                position: 'absolute',
                                inset: 0,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                pointerEvents: 'none',
                                zIndex: 1,
                            }}
                        >
                            <Text c="dimmed" size="sm">
                                Нет данных за выбранный период
                            </Text>
                        </div>
                    )}
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
                            domain={[startMs, endMs]}
                            allowDataOverflow
                            ticks={xTicks}
                            tickFormatter={tickFormatter}
                            tick={{ fontSize: 11 }}
                        />
                        <YAxis
                            tick={{ fontSize: 11 }}
                            width={65}
                            domain={hasAnyValue ? ['auto', 'auto'] : [0, 1]}
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
                            stroke={dotColor}
                            fill="url(#trendGrad)"
                            strokeWidth={2}
                            dot={renderIsolatedDot}
                            activeDot={{ r: 4 }}
                            isAnimationActive={false}
                            connectNulls={false}
                        />
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
                </div>
            )}
        </Card>
    );
}
