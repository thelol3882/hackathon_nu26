'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import {
    Card, Text, Group, Select, SegmentedControl, Loader, Center, ActionIcon,
    Tooltip as MantineTooltip, Badge,
} from '@mantine/core';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    ReferenceArea, ReferenceLine,
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

// Ranges: window size shown on X axis. Bucket interval auto-picked for smooth chart.
const rangeOptions = [
    { label: '5м', value: '5m' },
    { label: '15м', value: '15m' },
    { label: '30м', value: '30m' },
    { label: '1ч', value: '1h' },
    { label: '3ч', value: '3h' },
    { label: '6ч', value: '6h' },
    { label: '12ч', value: '12h' },
    { label: '24ч', value: '24h' },
];

const rangeConfig: Record<string, { getStart: () => string; bucket_interval: BucketInterval; tickCount: number }> = {
    '5m':  { getStart: () => minutesAgo(5),  bucket_interval: '1 minute',   tickCount: 5 },
    '15m': { getStart: () => minutesAgo(15), bucket_interval: '1 minute',   tickCount: 8 },
    '30m': { getStart: () => minutesAgo(30), bucket_interval: '1 minute',   tickCount: 7 },
    '1h':  { getStart: () => hoursAgo(1),    bucket_interval: '5 minutes',  tickCount: 7 },
    '3h':  { getStart: () => hoursAgo(3),    bucket_interval: '10 minutes', tickCount: 7 },
    '6h':  { getStart: () => hoursAgo(6),    bucket_interval: '15 minutes', tickCount: 7 },
    '12h': { getStart: () => hoursAgo(12),   bucket_interval: '30 minutes', tickCount: 7 },
    '24h': { getStart: () => hoursAgo(24),   bucket_interval: '1 hour',     tickCount: 8 },
};

function toEpoch(bucket: string): number { return new Date(bucket).getTime(); }

function fmtTick(v: number): string {
    const d = new Date(v);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function CustomTooltipContent({ active, payload, label, unit, sensorLabel }: {
    active?: boolean;
    payload?: Array<{ value: number | null; payload: { min_value: number | null; max_value: number | null } }>;
    label?: string; unit: string; sensorLabel: string;
}) {
    if (!active || !payload?.length) return null;
    const d = payload[0];
    const avg = d.value;
    if (avg == null) return null;
    const min = d.payload.min_value;
    const max = d.payload.max_value;
    return (
        <div style={{ background: 'var(--dashboard-surface)', border: '1px solid var(--dashboard-border)', borderRadius: 8, padding: '8px 12px', fontSize: 12, lineHeight: 1.6, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
            <div style={{ fontWeight: 600, marginBottom: 2, color: 'var(--dashboard-text-secondary)' }}>
                {formatTime(new Date(Number(label)))}
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

export default function TrendsPanel({ locomotiveId }: TrendsPanelProps) {
    const [selectedSensor, setSelectedSensor] = useState('speed_actual');
    const [selectedRange, setSelectedRange] = useState('15m');
    const [pollTick, setPollTick] = useState(0);

    const [zoomLeft, setZoomLeft] = useState<string | null>(null);
    const [zoomRight, setZoomRight] = useState<string | null>(null);
    const [zoomedDomain, setZoomedDomain] = useState<[number, number] | null>(null);

    useEffect(() => {
        const id = setInterval(() => setPollTick((t) => t + 1), 30_000);
        return () => clearInterval(id);
    }, []);

    useEffect(() => { setZoomedDomain(null); }, [selectedRange, selectedSensor, locomotiveId]);

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

    const chartData = useMemo(() => {
        if (!data?.length) return [];
        return data.map((d) => ({ ...d, ts: toEpoch(d.bucket) }));
    }, [data]);

    const unit = data?.find((d) => d.unit)?.unit ?? '';
    const sensorLabel = sensorLabels[selectedSensor] ?? selectedSensor;
    const tickCount = rangeConfig[selectedRange].tickCount;

    const stats = useMemo(() => {
        if (!chartData.length) return null;
        const values = chartData.map((d) => d.avg_value).filter((v): v is number => v != null);
        if (!values.length) return null;
        const avg = values.reduce((a, b) => a + b, 0) / values.length;
        return { avg, min: Math.min(...values), max: Math.max(...values) };
    }, [chartData]);

    const handleMouseDown = useCallback((e: { activeLabel?: string | number }) => { if (e?.activeLabel != null) setZoomLeft(String(e.activeLabel)); }, []);
    const handleMouseMove = useCallback((e: { activeLabel?: string | number }) => { if (zoomLeft && e?.activeLabel != null) setZoomRight(String(e.activeLabel)); }, [zoomLeft]);
    const handleMouseUp = useCallback(() => {
        if (zoomLeft && zoomRight) { const l = Number(zoomLeft), r = Number(zoomRight); if (l !== r) setZoomedDomain([Math.min(l, r), Math.max(l, r)]); }
        setZoomLeft(null); setZoomRight(null);
    }, [zoomLeft, zoomRight]);
    const resetZoom = useCallback(() => setZoomedDomain(null), []);

    const xDomain = useMemo<[number, number] | undefined>(() => {
        if (zoomedDomain) return zoomedDomain;
        if (!chartData.length) return undefined;
        return [chartData[0].ts, chartData[chartData.length - 1].ts];
    }, [chartData, zoomedDomain]);

    return (
        <Card style={{ borderTop: '2px solid var(--mantine-color-ktzBlue-5)' }}>
            <Group justify="space-between" mb="xs" wrap="wrap" gap="xs">
                <Group gap="xs">
                    <Text className="panel-label">ТРЕНДЫ</Text>
                    {zoomedDomain && (
                        <MantineTooltip label="Сбросить зум">
                            <ActionIcon variant="subtle" size="xs" onClick={resetZoom} color="ktzBlue">↻</ActionIcon>
                        </MantineTooltip>
                    )}
                    {isFetching && <Loader size={12} />}
                </Group>
                <Group gap="xs" wrap="wrap">
                    <Select size="xs" value={selectedSensor} onChange={(v) => v && setSelectedSensor(v)} data={sensorOptions} w={180} searchable placeholder="Датчик" />
                </Group>
            </Group>

            {/* Time range selector */}
            <SegmentedControl size="xs" value={selectedRange} onChange={setSelectedRange} data={rangeOptions} mb="sm" fullWidth />

            {stats && (
                <Group gap="xs" mb="xs">
                    <Badge size="xs" variant="light" color="ktzBlue">Сред: {stats.avg.toFixed(1)} {unit}</Badge>
                    <Badge size="xs" variant="light" color="green">Мин: {stats.min.toFixed(1)} {unit}</Badge>
                    <Badge size="xs" variant="light" color="critical">Макс: {stats.max.toFixed(1)} {unit}</Badge>
                </Group>
            )}

            {!locomotiveId ? (
                <Center h={280}><Text c="dimmed">Выберите локомотив</Text></Center>
            ) : isFetching && !data ? (
                <Center h={280}><Loader size="sm" /></Center>
            ) : !data || data.length === 0 ? (
                <Center h={280}><Text c="dimmed">Нет данных</Text></Center>
            ) : (
                <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={chartData} onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp}>
                        <defs>
                            <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="var(--mantine-color-ktzBlue-5)" stopOpacity={0.3} />
                                <stop offset="100%" stopColor="var(--mantine-color-ktzBlue-5)" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--dashboard-border)" />
                        <XAxis dataKey="ts" type="number" scale="time" domain={xDomain} tickCount={tickCount} tickFormatter={fmtTick} tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} width={65} domain={['auto', 'auto']} allowDecimals={false} tickFormatter={(v: number) => `${v}${unit ? ` ${unit}` : ''}`} />
                        <Tooltip content={<CustomTooltipContent unit={unit} sensorLabel={sensorLabel} />} />
                        {stats && <ReferenceLine y={stats.avg} stroke="var(--mantine-color-ktzGold-5)" strokeDasharray="5 5" strokeOpacity={0.5} />}
                        <Area type="monotone" dataKey="avg_value" stroke="var(--mantine-color-ktzBlue-5)" fill="url(#trendGradient)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
                        {zoomLeft && zoomRight && <ReferenceArea x1={Number(zoomLeft)} x2={Number(zoomRight)} strokeOpacity={0.3} fill="var(--mantine-color-ktzBlue-2)" fillOpacity={0.3} />}
                    </AreaChart>
                </ResponsiveContainer>
            )}
        </Card>
    );
}
