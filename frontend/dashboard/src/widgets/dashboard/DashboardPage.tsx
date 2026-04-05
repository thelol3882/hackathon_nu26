'use client';

import { useMemo } from 'react';
import { Box, Text, Center, Loader, Group, Badge, Stack, ThemeIcon, Slider } from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { IconTrain, IconPlayerPlay, IconBroadcast } from '@tabler/icons-react';
import { ActionIcon, Tooltip } from '@mantine/core';
import { useLocomotive } from '@/widgets/layout/LocomotiveContext';
import { useLiveTelemetry, useGetTelemetrySnapshotQuery } from '@/features/telemetry';
import { useHealthIndex } from '@/features/health';
import { healthApi } from '@/features/health/api/healthApi';
import { useLiveAlerts } from '@/features/alerts';
import { alertsApi } from '@/features/alerts/api/alertsApi';
import type { SensorType, TelemetryReading } from '@/features/telemetry/types';
import { getRelativeTime, formatDateTime, dayjs } from '@/shared/utils/date';

import { HealthIndexGauge } from './components/HealthIndexGauge/HealthIndexGauge';
import SpeedPanel from './components/SpeedPanel/SpeedPanel';
import FuelEnergyPanel from './components/FuelEnergyPanel/FuelEnergyPanel';
import PressureTemperaturePanel from './components/PressureTemperaturePanel/PressureTemperaturePanel';
import ElectricalPanel from './components/ElectricalPanel/ElectricalPanel';
import AlertsPanel from './components/AlertsPanel/AlertsPanel';
import TrendsPanel from './components/TrendsPanel/TrendsPanel';
import { RouteMap } from './components/RouteMap/RouteMap';

import styles from './DashboardPage.module.css';

function StatusStrip({
    locomotiveId,
    locomotiveLabel,
    connectionStatus,
    latestTimestamp,
    sensorCount,
}: {
    locomotiveId: string;
    locomotiveLabel: string | null;
    connectionStatus: string;
    latestTimestamp: string | null;
    sensorCount: number;
}) {
    const connected = connectionStatus === 'connected';
    const reconnecting = connectionStatus === 'reconnecting';
    return (
        <Box className={styles.statusStrip}>
            <Group px="md" py={8} justify="space-between">
                {/* Left: loco info */}
                <Group gap="sm">
                    <IconTrain size={14} style={{ opacity: 0.5 }} />
                    <Text
                        size="xs"
                        fw={600}
                        ff="var(--font-mono), monospace"
                        c="var(--dashboard-text-primary)"
                    >
                        {locomotiveLabel ?? locomotiveId.slice(0, 8)}
                    </Text>
                    <div
                        style={{
                            width: 1,
                            height: 14,
                            background: 'var(--dashboard-border)',
                        }}
                    />
                    <Badge
                        size="xs"
                        variant="dot"
                        color={connected ? 'green' : reconnecting ? 'yellow' : 'red'}
                    >
                        {connected ? 'Онлайн' : reconnecting ? 'Переподкл.' : 'Нет связи'}
                    </Badge>
                </Group>

                {/* Right: meta */}
                <Group gap="sm">
                    {latestTimestamp && (
                        <Text size="xs" c="dimmed" ff="var(--font-mono), monospace">
                            {getRelativeTime(latestTimestamp)}
                        </Text>
                    )}
                    <Text size="xs" c="dimmed">
                        {sensorCount} датчиков
                    </Text>
                </Group>
            </Group>
        </Box>
    );
}

function EmptyDashboard() {
    return (
        <Center h="70vh">
            <Stack align="center" gap="lg">
                <div className={styles.emptyIcon}>
                    <ThemeIcon
                        size={80}
                        radius="xl"
                        variant="light"
                        color="ktzBlue"
                        style={{ opacity: 0.8 }}
                    >
                        <IconTrain size={40} stroke={1.2} />
                    </ThemeIcon>
                </div>
                <Stack align="center" gap={4}>
                    <Text size="xl" fw={600}>
                        Выберите локомотив
                    </Text>
                    <Text size="md" c="var(--dashboard-text-secondary)" ta="center" maw={400}>
                        Выберите локомотив из списка в верхней панели для отображения телеметрии
                    </Text>
                </Stack>
                <Group gap="xs">
                    <Badge variant="light" color="ktzBlue" size="lg">
                        TE33A
                    </Badge>
                    <Text c="dimmed" size="sm">
                        или
                    </Text>
                    <Badge variant="light" color="ktzCyan" size="lg">
                        KZ8A
                    </Badge>
                </Group>
            </Stack>
        </Center>
    );
}

function ReplayControls() {
    const { replay, setReplay } = useLocomotive();

    const toggleReplay = () => {
        if (replay.enabled) {
            setReplay({ enabled: false, start: null, end: null, cursor: null });
        } else {
            const end = dayjs().toISOString();
            const start = dayjs().subtract(15, 'minute').toISOString();
            setReplay({ enabled: true, start, end, cursor: end });
        }
    };

    const handleCursorChange = (pct: number) => {
        if (!replay.start || !replay.end) return;
        const startMs = dayjs(replay.start).valueOf();
        const endMs = dayjs(replay.end).valueOf();
        const cursorMs = startMs + (endMs - startMs) * (pct / 100);
        setReplay({ ...replay, cursor: dayjs(cursorMs).toISOString() });
    };

    const cursorPct = useMemo(() => {
        if (!replay.start || !replay.end || !replay.cursor) return 100;
        const startMs = dayjs(replay.start).valueOf();
        const endMs = dayjs(replay.end).valueOf();
        const cursorMs = dayjs(replay.cursor).valueOf();
        const range = endMs - startMs;
        if (range <= 0) return 100;
        return ((cursorMs - startMs) / range) * 100;
    }, [replay]);

    return (
        <Box className={styles.replayBar}>
            <Group px="md" py={6} justify="space-between" wrap="wrap" gap="xs">
                <Group gap="sm">
                    <Tooltip label={replay.enabled ? 'Вернуться к Live' : 'Режим перемотки'}>
                        <ActionIcon
                            variant={replay.enabled ? 'filled' : 'light'}
                            color={replay.enabled ? 'ktzGold' : 'gray'}
                            size="md"
                            onClick={toggleReplay}
                        >
                            {replay.enabled ? (
                                <IconBroadcast size={16} />
                            ) : (
                                <IconPlayerPlay size={16} />
                            )}
                        </ActionIcon>
                    </Tooltip>

                    {replay.enabled ? (
                        <Badge
                            size="sm"
                            variant="filled"
                            color="ktzGold"
                            leftSection={<IconPlayerPlay size={10} />}
                        >
                            REPLAY
                        </Badge>
                    ) : (
                        <Badge size="sm" variant="dot" color="green">
                            LIVE
                        </Badge>
                    )}
                </Group>

                {replay.enabled && (
                    <Group gap="sm" wrap="wrap" style={{ flex: 1 }}>
                        <DateTimePicker
                            size="xs"
                            value={replay.start}
                            onChange={(v) => v && setReplay({ ...replay, start: v, cursor: v })}
                            maxDate={dayjs().toDate()}
                            w={170}
                            placeholder="Начало"
                        />
                        <DateTimePicker
                            size="xs"
                            value={replay.end}
                            onChange={(v) => v && setReplay({ ...replay, end: v })}
                            maxDate={dayjs().toDate()}
                            w={170}
                            placeholder="Конец"
                        />
                    </Group>
                )}

                {replay.enabled && replay.cursor && (
                    <Text size="xs" c="ktzGold" ff="var(--font-mono), monospace" fw={600}>
                        {formatDateTime(replay.cursor)}
                    </Text>
                )}
            </Group>

            {/* Timeline slider */}
            {replay.enabled && replay.start && replay.end && (
                <Box px="md" pb={6}>
                    <Slider
                        value={cursorPct}
                        onChange={handleCursorChange}
                        min={0}
                        max={100}
                        step={0.5}
                        size="xs"
                        color="ktzGold"
                        label={(v) => {
                            if (!replay.start || !replay.end) return '';
                            const sMs = dayjs(replay.start).valueOf();
                            const eMs = dayjs(replay.end).valueOf();
                            return dayjs(sMs + (eMs - sMs) * (v / 100)).format('HH:mm:ss');
                        }}
                        marks={[
                            {
                                value: 0,
                                label: replay.start ? dayjs(replay.start).format('HH:mm') : '',
                            },
                            { value: 50 },
                            {
                                value: 100,
                                label: replay.end ? dayjs(replay.end).format('HH:mm') : '',
                            },
                        ]}
                    />
                </Box>
            )}
        </Box>
    );
}

function LiveDashboardContent({ locomotiveId }: { locomotiveId: string }) {
    const { locomotiveLabel } = useLocomotive();
    const { sensors, position, connectionStatus } = useLiveTelemetry(locomotiveId);
    const { health, isLoading: healthLoading } = useHealthIndex(locomotiveId);
    const { alerts, clearAlerts } = useLiveAlerts(locomotiveId);
    const getSensor = (type: SensorType) => sensors.get(type);
    const locoType = health?.locomotive_type ?? sensors.values().next().value?.locomotive_type;

    if (healthLoading && sensors.size === 0) {
        return (
            <Center h="50vh">
                <Stack align="center" gap="md">
                    <Loader size="lg" color="ktzBlue" />
                    <Text size="sm" c="dimmed">
                        Подключение...
                    </Text>
                </Stack>
            </Center>
        );
    }

    const latestTimestamp = Array.from(sensors.values()).reduce<string | null>((latest, s) => {
        if (!latest || s.timestamp > latest) return s.timestamp;
        return latest;
    }, null);

    return (
        <>
            <StatusStrip
                locomotiveId={locomotiveId}
                locomotiveLabel={locomotiveLabel}
                connectionStatus={connectionStatus}
                latestTimestamp={latestTimestamp}
                sensorCount={sensors.size}
            />
            <DashboardGrid
                getSensor={getSensor}
                health={health}
                healthLoading={healthLoading}
                locoType={locoType}
                alerts={alerts}
                clearAlerts={clearAlerts}
                locomotiveId={locomotiveId}
                position={position}
                isReplay={false}
            />
        </>
    );
}

function ReplayDashboardContent({ locomotiveId }: { locomotiveId: string }) {
    const { replay, locomotiveLabel } = useLocomotive();
    const cursorIso = replay.cursor ? dayjs(replay.cursor).toISOString() : '';

    // Fetch snapshot telemetry at cursor time
    const { data: snapshot, isFetching: snapFetching } = useGetTelemetrySnapshotQuery(
        { locomotive_id: locomotiveId, at: cursorIso },
        { skip: !cursorIso },
    );

    // Fetch health at cursor time
    const { data: health, isFetching: healthFetching } = healthApi.useGetHealthAtQuery(
        { locomotiveId, at: cursorIso },
        { skip: !cursorIso },
    );

    // Fetch alerts in replay window
    const startIso = replay.start ? dayjs(replay.start).toISOString() : undefined;
    const endIso = replay.cursor ? dayjs(replay.cursor).toISOString() : undefined;
    const { data: alerts = [] } = alertsApi.useGetAlertsQuery(
        { locomotive_id: locomotiveId, start: startIso, end: endIso, limit: 50 },
        { skip: !startIso || !endIso },
    );

    // Build sensor map from snapshot
    const sensorMap = useMemo(() => {
        const map = new Map<string, TelemetryReading>();
        if (!snapshot) return map;
        for (const s of snapshot) {
            map.set(s.sensor_type, {
                locomotive_id: s.locomotive_id,
                locomotive_type: s.locomotive_type,
                sensor_type: s.sensor_type,
                value: s.value,
                filtered_value: s.filtered_value,
                unit: s.unit,
                timestamp: s.timestamp,
                latitude: s.latitude,
                longitude: s.longitude,
            });
        }
        return map;
    }, [snapshot]);

    const getSensor = (type: SensorType) => sensorMap.get(type);
    const locoType = health?.locomotive_type ?? snapshot?.[0]?.locomotive_type;

    const position = useMemo(() => {
        if (!snapshot) return null;
        const withGps = snapshot.find((s) => s.latitude != null && s.longitude != null);
        return withGps ? { latitude: withGps.latitude!, longitude: withGps.longitude! } : null;
    }, [snapshot]);

    const isLoading = snapFetching || healthFetching;

    if (isLoading && sensorMap.size === 0) {
        return (
            <Center h="50vh">
                <Stack align="center" gap="md">
                    <Loader size="lg" color="ktzGold" />
                    <Text size="sm" c="dimmed">
                        Загрузка данных за {replay.cursor ? formatDateTime(replay.cursor) : '...'}
                        ...
                    </Text>
                </Stack>
            </Center>
        );
    }

    return (
        <>
            <Box
                className={styles.statusStrip}
                style={{ borderColor: 'var(--mantine-color-ktzGold-5)' }}
            >
                <Group px="md" py={8} justify="space-between">
                    <Group gap="sm">
                        <IconTrain size={14} style={{ opacity: 0.5 }} />
                        <Text size="xs" fw={600} ff="var(--font-mono), monospace">
                            {locomotiveLabel ?? locomotiveId.slice(0, 8)}
                        </Text>
                        <div
                            style={{ width: 1, height: 14, background: 'var(--dashboard-border)' }}
                        />
                        <Badge size="xs" variant="filled" color="ktzGold">
                            REPLAY
                        </Badge>
                    </Group>
                    <Group gap="sm">
                        <Text size="xs" fw={600} c="ktzGold" ff="var(--font-mono), monospace">
                            {replay.cursor ? formatDateTime(replay.cursor) : ''}
                        </Text>
                        <Text size="xs" c="dimmed">
                            {sensorMap.size} датчиков
                        </Text>
                    </Group>
                </Group>
            </Box>
            <DashboardGrid
                getSensor={getSensor}
                health={health ?? null}
                healthLoading={isLoading}
                locoType={locoType}
                alerts={alerts}
                clearAlerts={() => {}}
                locomotiveId={locomotiveId}
                position={position}
                isReplay={true}
                replayStart={replay.start ? dayjs(replay.start).toISOString() : undefined}
                replayEnd={replay.end ? dayjs(replay.end).toISOString() : undefined}
            />
        </>
    );
}

interface DashboardGridProps {
    getSensor: (type: SensorType) => TelemetryReading | undefined;
    health: import('@/features/health/types').HealthIndex | null;
    healthLoading: boolean;
    locoType: string | undefined;
    alerts: import('@/features/alerts/types').AlertEvent[];
    clearAlerts: () => void;
    locomotiveId: string;
    position: { latitude: number; longitude: number } | null;
    isReplay?: boolean;
    replayStart?: string;
    replayEnd?: string;
}

function DashboardGrid({
    getSensor,
    health,
    healthLoading,
    locoType,
    alerts,
    clearAlerts,
    locomotiveId,
    position,
    isReplay,
    replayStart,
    replayEnd,
}: DashboardGridProps) {
    return (
        <Box className={styles.grid}>
            <Box className={styles.health}>
                <HealthIndexGauge health={health} isLoading={healthLoading} />
            </Box>
            <Box className={styles.speed}>
                <SpeedPanel
                    speedActual={getSensor('speed_actual')}
                    speedTarget={getSensor('speed_target')}
                />
            </Box>
            <Box className={styles.fuel}>
                <FuelEnergyPanel
                    locomotiveType={locoType}
                    fuelLevel={getSensor('fuel_level')}
                    fuelRate={getSensor('fuel_rate')}
                    catenaryVoltage={getSensor('catenary_voltage')}
                    pantographCurrent={getSensor('pantograph_current')}
                />
            </Box>
            <Box className={styles.press}>
                <PressureTemperaturePanel
                    coolantTemp={getSensor('coolant_temp')}
                    oilPressure={getSensor('oil_pressure')}
                    brakePipePressure={getSensor('brake_pipe_pressure')}
                />
            </Box>
            <Box className={styles.elec}>
                <ElectricalPanel
                    locomotiveType={locoType}
                    tractionMotorTemp={getSensor('traction_motor_temp')}
                    crankcasePressure={getSensor('crankcase_pressure')}
                    dieselRpm={getSensor('diesel_rpm')}
                    transformerTemp={getSensor('transformer_temp')}
                    igbtTemp={getSensor('igbt_temp')}
                    dcLinkVoltage={getSensor('dc_link_voltage')}
                    recuperationCurrent={getSensor('recuperation_current')}
                />
            </Box>
            <Box className={styles.alerts}>
                <AlertsPanel alerts={alerts} onClear={clearAlerts} isReplay={isReplay} />
            </Box>
            <Box className={styles.trends}>
                <TrendsPanel
                    locomotiveId={locomotiveId}
                    replayStart={replayStart}
                    replayEnd={replayEnd}
                />
            </Box>
            <Box className={styles.map}>
                <RouteMap position={position} />
            </Box>
        </Box>
    );
}

export function DashboardPage() {
    const { locomotiveId, replay } = useLocomotive();

    if (!locomotiveId) return <EmptyDashboard />;

    return (
        <>
            <ReplayControls />
            {replay.enabled && replay.cursor ? (
                <ReplayDashboardContent locomotiveId={locomotiveId} />
            ) : (
                <LiveDashboardContent locomotiveId={locomotiveId} />
            )}
        </>
    );
}
