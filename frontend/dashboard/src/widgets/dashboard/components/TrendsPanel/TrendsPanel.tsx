'use client';

import { useState, useMemo } from 'react';
import { Card, Text, Group, Select, SegmentedControl, Loader, Center } from '@mantine/core';
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from 'recharts';
import { useGetTelemetryQuery } from '@/features/telemetry';
import type { BucketInterval } from '@/features/telemetry';
import { minutesAgo, hoursAgo, formatTimeShort } from '@/shared/utils/date';

interface TrendsPanelProps {
    locomotiveId: string | null;
}

const sensorOptions = [
    { value: 'speed_actual', label: 'Скорость' },
    { value: 'coolant_temp', label: 'Темп. охлаждения' },
    { value: 'oil_pressure', label: 'Давление масла' },
    { value: 'diesel_rpm', label: 'Обороты дизеля' },
    { value: 'fuel_level', label: 'Уровень топлива' },
    { value: 'brake_pipe_pressure', label: 'Давл. тормозной магистрали' },
];

const rangeOptions = [
    { label: '5м', value: '5m' },
    { label: '15м', value: '15m' },
    { label: '1ч', value: '1h' },
    { label: '24ч', value: '24h' },
];

const rangeConfig: Record<string, { getStart: () => string; bucket_interval: BucketInterval }> = {
    '5m': { getStart: () => minutesAgo(5), bucket_interval: '1 minute' },
    '15m': { getStart: () => minutesAgo(15), bucket_interval: '1 minute' },
    '1h': { getStart: () => hoursAgo(1), bucket_interval: '5 minutes' },
    '24h': { getStart: () => hoursAgo(24), bucket_interval: '1 hour' },
};

export default function TrendsPanel({ locomotiveId }: TrendsPanelProps) {
    const [selectedSensor, setSelectedSensor] = useState('speed_actual');
    const [selectedRange, setSelectedRange] = useState('15m');

    const queryParams = useMemo(() => {
        const cfg = rangeConfig[selectedRange];
        return {
            locomotive_id: locomotiveId ?? undefined,
            sensor_type: selectedSensor,
            start: cfg.getStart(),
            bucket_interval: cfg.bucket_interval,
            limit: 500,
        };
    }, [locomotiveId, selectedSensor, selectedRange]);

    const { data, isFetching } = useGetTelemetryQuery(queryParams, {
        skip: !locomotiveId,
        pollingInterval: 30000,
    });

    const unit = data?.[0]?.unit ?? '';

    return (
        <Card style={{ borderTop: '2px solid var(--mantine-color-ktzBlue-5)' }}>
            <Group justify="space-between" mb="sm" wrap="wrap" gap="xs">
                <Text className="panel-label">ТРЕНДЫ</Text>
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
                <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={data}>
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
                        <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="var(--dashboard-border)"
                        />
                        <XAxis
                            dataKey="bucket"
                            tickFormatter={(v: string) => formatTimeShort(v)}
                            tick={{ fontSize: 11 }}
                        />
                        <YAxis
                            unit={unit ? ` ${unit}` : ''}
                            tick={{ fontSize: 11 }}
                            width={60}
                        />
                        <Tooltip
                            formatter={(value: unknown) => [
                                `${Number(value).toFixed(2)} ${unit}`,
                                'Среднее',
                            ]}
                            labelFormatter={(label: unknown) => formatTimeShort(String(label))}
                        />
                        <Area
                            type="monotone"
                            dataKey="avg_value"
                            stroke="var(--mantine-color-ktzBlue-5)"
                            fill="url(#trendGradient)"
                            strokeWidth={2}
                            dot={false}
                            isAnimationActive={false}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            )}
        </Card>
    );
}
