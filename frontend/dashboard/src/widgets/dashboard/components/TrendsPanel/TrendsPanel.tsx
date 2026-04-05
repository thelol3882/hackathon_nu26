'use client';

import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import {
    Card, Text, Group, Select, SegmentedControl, Loader, Center, Badge, Box,
    Tooltip as MantineTooltip, ActionIcon,
} from '@mantine/core';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    ReferenceLine,
} from 'recharts';
import { IconChevronLeft } from '@tabler/icons-react';
import { useGetTelemetryQuery } from '@/features/telemetry';
import type { BucketInterval } from '@/features/telemetry';
import { formatTime, dayjs } from '@/shared/utils/date';

interface TrendsPanelProps {
    locomotiveId: string | null;
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

// Step = bucket_interval on X axis. Each point = one aggregated bucket.
const stepOptions = [
    { label: '1м', value: '1m' },
    { label: '5м', value: '5m' },
    { label: '15м', value: '15m' },
    { label: '30м', value: '30m' },
    { label: '1ч', value: '1h' },
    { label: '6ч', value: '6h' },
];

const stepConfig: Record<string, { bucket_interval: BucketInterval; initialPoints: number; stepMs: number; refreshMs: number }> = {
    '1m':  { bucket_interval: '1 minute',   initialPoints: 40, stepMs: 60_000,       refreshMs: 15_000 },
    '5m':  { bucket_interval: '5 minutes',  initialPoints: 40, stepMs: 300_000,      refreshMs: 30_000 },
    '15m': { bucket_interval: '15 minutes', initialPoints: 40, stepMs: 900_000,      refreshMs: 60_000 },
    '30m': { bucket_interval: '30 minutes', initialPoints: 36, stepMs: 1_800_000,    refreshMs: 60_000 },
    '1h':  { bucket_interval: '1 hour',     initialPoints: 30, stepMs: 3_600_000,    refreshMs: 120_000 },
    '6h':  { bucket_interval: '1 hour',     initialPoints: 36, stepMs: 21_600_000,   refreshMs: 300_000 },
};

const LOAD_MORE_POINTS = 30;

function toEpoch(bucket: string): number { return new Date(bucket).getTime(); }

/** Format tick — show HH:mm, and date when day changes */
function fmtTickWithDate(v: number, _i: number, data: Array<{ ts: number }>): string {
    const d = dayjs(v);
    return d.format('HH:mm');
}

function CustomTooltipContent({ active, payload, label, unit, sensorLabel }: {
    active?: boolean;
    payload?: Array<{ value: number | null; payload: { min_value: number | null; max_value: number | null; ts: number } }>;
    label?: string; unit: string; sensorLabel: string;
}) {
    if (!active || !payload?.length) return null;
    const d = payload[0];
    const avg = d.value;
    if (avg == null) return null;
    const ts = d.payload.ts;
    const min = d.payload.min_value;
    const max = d.payload.max_value;
    return (
        <div style={{ background: 'var(--dashboard-surface)', border: '1px solid var(--dashboard-border)', borderRadius: 8, padding: '8px 12px', fontSize: 12, lineHeight: 1.6, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
            <div style={{ fontWeight: 600, marginBottom: 2, color: 'var(--dashboard-text-secondary)' }}>
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

/** Custom X axis tick that shows date label when day changes */
function DateAwareXTick({ x, y, payload, data }: { x: number; y: number; payload: { value: number; index: number }; data: Array<{ ts: number }> }) {
    const val = payload.value;
    const d = dayjs(val);
    const timeStr = d.format('HH:mm');

    // Show date label if this is the first point or the day changed from previous
    let showDate = false;
    if (payload.index === 0) {
        showDate = true;
    } else if (data.length > 0 && payload.index < data.length) {
        const prevTs = data[payload.index - 1]?.ts;
        if (prevTs) {
            const prevDay = dayjs(prevTs).format('DD.MM');
            const curDay = d.format('DD.MM');
            if (prevDay !== curDay) showDate = true;
        }
    }

    return (
        <g transform={`translate(${x},${y})`}>
            {showDate && (
                <text x={0} y={-4} textAnchor="middle" fill="var(--mantine-color-ktzGold-5)" fontSize={9} fontWeight={600}>
                    {d.format('DD.MM')}
                </text>
            )}
            <text x={0} y={12} textAnchor="middle" fill="var(--dashboard-text-secondary)" fontSize={10}>
                {timeStr}
            </text>
        </g>
    );
}

export default function TrendsPanel({ locomotiveId }: TrendsPanelProps) {
    const [selectedSensor, setSelectedSensor] = useState('speed_actual');
    const [selectedStep, setSelectedStep] = useState('5m');
    const [pollTick, setPollTick] = useState(0);

    // Accumulated data points (sorted by ts ASC)
    const [allData, setAllData] = useState<Array<{ ts: number; bucket: string; avg_value: number | null; min_value: number | null; max_value: number | null; unit: string }>>([]);
    const [loadingMore, setLoadingMore] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const didInitialScroll = useRef(false);

    const cfg = stepConfig[selectedStep];

    // Calculate start time for initial load
    const startIso = useMemo(() => {
        return dayjs().subtract(cfg.initialPoints * cfg.stepMs, 'millisecond').toISOString();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedStep, selectedSensor, locomotiveId]);

    // Initial data fetch
    const { data: freshData, isFetching } = useGetTelemetryQuery(
        {
            locomotive_id: locomotiveId ?? undefined,
            sensor_type: selectedSensor,
            start: startIso,
            bucket_interval: cfg.bucket_interval,
            limit: cfg.initialPoints + 5,
        },
        {
            skip: !locomotiveId,
            pollingInterval: cfg.refreshMs,
        },
    );

    // Oldest loaded timestamp for "load more"
    const oldestTs = allData.length > 0 ? allData[0].ts : null;

    // Load more (older) data
    const olderStartIso = useMemo(() => {
        if (!oldestTs) return null;
        return dayjs(oldestTs).subtract(LOAD_MORE_POINTS * cfg.stepMs, 'millisecond').toISOString();
    }, [oldestTs, cfg.stepMs]);

    const olderEndIso = useMemo(() => {
        if (!oldestTs) return null;
        return dayjs(oldestTs).toISOString();
    }, [oldestTs]);

    const { data: olderData, isFetching: olderFetching } = useGetTelemetryQuery(
        {
            locomotive_id: locomotiveId ?? undefined,
            sensor_type: selectedSensor,
            start: olderStartIso!,
            end: olderEndIso!,
            bucket_interval: cfg.bucket_interval,
            limit: LOAD_MORE_POINTS + 5,
        },
        { skip: !loadingMore || !olderStartIso || !olderEndIso || !locomotiveId },
    );

    // When fresh data arrives, rebuild allData
    useEffect(() => {
        if (!freshData?.length) { setAllData([]); return; }
        const mapped = freshData
            .map((d) => ({ ts: toEpoch(d.bucket), bucket: typeof d.bucket === 'string' ? d.bucket : new Date(d.bucket).toISOString(), avg_value: d.avg_value, min_value: d.min_value, max_value: d.max_value, unit: d.unit }))
            .filter((d) => d.avg_value != null);
        // Merge with existing older data (keep points that are before fresh range)
        setAllData((prev) => {
            if (prev.length === 0) return mapped;
            const freshMinTs = mapped.length > 0 ? mapped[0].ts : Infinity;
            const olderPart = prev.filter((p) => p.ts < freshMinTs);
            return [...olderPart, ...mapped];
        });
        didInitialScroll.current = false;
    }, [freshData]);

    // When older data arrives, prepend
    useEffect(() => {
        if (!olderData?.length || !loadingMore) return;
        const mapped = olderData
            .map((d) => ({ ts: toEpoch(d.bucket), bucket: typeof d.bucket === 'string' ? d.bucket : new Date(d.bucket).toISOString(), avg_value: d.avg_value, min_value: d.min_value, max_value: d.max_value, unit: d.unit }))
            .filter((d) => d.avg_value != null);
        setAllData((prev) => {
            const existingTsSet = new Set(prev.map((p) => p.ts));
            const newPoints = mapped.filter((m) => !existingTsSet.has(m.ts));
            return [...newPoints, ...prev].sort((a, b) => a.ts - b.ts);
        });
        setLoadingMore(false);
    }, [olderData, loadingMore]);

    // Reset when sensor or step changes
    useEffect(() => {
        setAllData([]);
        setLoadingMore(false);
        didInitialScroll.current = false;
    }, [selectedSensor, selectedStep, locomotiveId]);

    // Auto-scroll to right on initial load
    useEffect(() => {
        if (allData.length > 0 && scrollRef.current && !didInitialScroll.current) {
            scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
            didInitialScroll.current = true;
        }
    }, [allData]);

    // Handle scroll — load more when near left edge
    const handleScroll = useCallback(() => {
        const el = scrollRef.current;
        if (!el || loadingMore || olderFetching) return;
        if (el.scrollLeft < 100 && allData.length > 0) {
            setLoadingMore(true);
        }
    }, [loadingMore, olderFetching, allData.length]);

    const unit = allData.find((d) => d.unit)?.unit ?? '';
    const sensorLabel = sensorLabels[selectedSensor] ?? selectedSensor;

    const stats = useMemo(() => {
        const values = allData.map((d) => d.avg_value).filter((v): v is number => v != null);
        if (!values.length) return null;
        const avg = values.reduce((a, b) => a + b, 0) / values.length;
        return { avg, min: Math.min(...values), max: Math.max(...values) };
    }, [allData]);

    // Chart width: each point gets ~40px
    const chartWidth = Math.max(600, allData.length * 40);

    return (
        <Card style={{ borderTop: '2px solid var(--mantine-color-ktzBlue-5)' }}>
            <Group justify="space-between" mb="xs" wrap="wrap" gap="xs">
                <Group gap="xs">
                    <Text className="panel-label">ТРЕНДЫ</Text>
                    {(isFetching || loadingMore) && <Loader size={12} />}
                </Group>
                <Select size="xs" value={selectedSensor} onChange={(v) => v && setSelectedSensor(v)} data={sensorOptions} w={180} searchable placeholder="Датчик" />
            </Group>

            {/* Step selector */}
            <Group gap="xs" mb="sm" justify="space-between">
                <Text size="xs" c="dimmed">Шаг:</Text>
                <SegmentedControl size="xs" value={selectedStep} onChange={setSelectedStep} data={stepOptions} />
            </Group>

            {stats && (
                <Group gap="xs" mb="xs">
                    <Badge size="xs" variant="light" color="ktzBlue">Сред: {stats.avg.toFixed(1)} {unit}</Badge>
                    <Badge size="xs" variant="light" color="green">Мин: {stats.min.toFixed(1)} {unit}</Badge>
                    <Badge size="xs" variant="light" color="critical">Макс: {stats.max.toFixed(1)} {unit}</Badge>
                    <Badge size="xs" variant="outline" color="gray">{allData.length} точек</Badge>
                </Group>
            )}

            {!locomotiveId ? (
                <Center h={280}><Text c="dimmed">Выберите локомотив</Text></Center>
            ) : isFetching && allData.length === 0 ? (
                <Center h={280}><Loader size="sm" /></Center>
            ) : allData.length === 0 ? (
                <Center h={280}><Text c="dimmed">Нет данных</Text></Center>
            ) : (
                <Box
                    ref={scrollRef}
                    onScroll={handleScroll}
                    style={{
                        overflowX: 'auto',
                        overflowY: 'hidden',
                        position: 'relative',
                    }}
                >
                    {/* Load more indicator */}
                    {loadingMore && (
                        <Box style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', zIndex: 10 }}>
                            <Loader size="xs" />
                        </Box>
                    )}
                    <div style={{ width: chartWidth, height: 300 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={allData} margin={{ top: 20, right: 10, bottom: 5, left: 0 }}>
                                <defs>
                                    <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="var(--mantine-color-ktzBlue-5)" stopOpacity={0.3} />
                                        <stop offset="100%" stopColor="var(--mantine-color-ktzBlue-5)" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--dashboard-border)" />
                                <XAxis
                                    dataKey="ts"
                                    type="number"
                                    scale="time"
                                    domain={['dataMin', 'dataMax']}
                                    tick={(props: any) => <DateAwareXTick {...props} data={allData} />}
                                    tickCount={Math.min(allData.length, 20)}
                                    height={30}
                                />
                                <YAxis tick={{ fontSize: 11 }} width={65} domain={['auto', 'auto']} tickFormatter={(v: number) => `${v}${unit ? ` ${unit}` : ''}`} />
                                <Tooltip content={<CustomTooltipContent unit={unit} sensorLabel={sensorLabel} />} />
                                {stats && <ReferenceLine y={stats.avg} stroke="var(--mantine-color-ktzGold-5)" strokeDasharray="5 5" strokeOpacity={0.4} />}
                                <Area type="monotone" dataKey="avg_value" stroke="var(--mantine-color-ktzBlue-5)" fill="url(#trendGradient)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </Box>
            )}
        </Card>
    );
}
