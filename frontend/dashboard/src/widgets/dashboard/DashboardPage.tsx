'use client';

import { Box, Text, Center, Loader, Group, Badge, Stack, ThemeIcon } from '@mantine/core';
import { IconTrain, IconWifi, IconWifiOff, IconActivity, IconClock } from '@tabler/icons-react';
import { useLocomotive } from '@/widgets/layout/LocomotiveContext';
import { useLiveTelemetry } from '@/features/telemetry';
import { useHealthIndex } from '@/features/health';
import { useLiveAlerts } from '@/features/alerts';
import type { SensorType } from '@/features/telemetry/types';
import { getRelativeTime } from '@/shared/utils/date';

import { HealthIndexGauge } from './components/HealthIndexGauge/HealthIndexGauge';
import SpeedPanel from './components/SpeedPanel/SpeedPanel';
import FuelEnergyPanel from './components/FuelEnergyPanel/FuelEnergyPanel';
import PressureTemperaturePanel from './components/PressureTemperaturePanel/PressureTemperaturePanel';
import ElectricalPanel from './components/ElectricalPanel/ElectricalPanel';
import AlertsPanel from './components/AlertsPanel/AlertsPanel';
import TrendsPanel from './components/TrendsPanel/TrendsPanel';
import { RouteMap } from './components/RouteMap/RouteMap';

import styles from './DashboardPage.module.css';

function ConnectionBadge({ status }: { status: string }) {
    const connected = status === 'connected';
    const reconnecting = status === 'reconnecting';
    return (
        <Badge
            size="sm"
            variant="dot"
            color={connected ? 'green' : reconnecting ? 'yellow' : 'red'}
            leftSection={connected ? <IconWifi size={10} /> : <IconWifiOff size={10} />}
        >
            {connected ? 'Онлайн' : reconnecting ? 'Переподключение...' : 'Нет связи'}
        </Badge>
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
                    <Text size="xl" fw={600} c="var(--dashboard-text-primary)">
                        Выберите локомотив
                    </Text>
                    <Text size="md" c="var(--dashboard-text-secondary)" ta="center" maw={400}>
                        Выберите локомотив из списка в верхней панели для отображения телеметрии в реальном времени
                    </Text>
                </Stack>
                <Group gap="xs">
                    <Badge variant="light" color="ktzBlue" size="lg">TE33A</Badge>
                    <Text c="dimmed" size="sm">или</Text>
                    <Badge variant="light" color="ktzCyan" size="lg">KZ8A</Badge>
                </Group>
            </Stack>
        </Center>
    );
}

export function DashboardPage() {
    const { locomotiveId } = useLocomotive();
    const { sensors, position, connectionStatus } = useLiveTelemetry(locomotiveId);
    const { health, isLoading: healthLoading } = useHealthIndex(locomotiveId);
    const { alerts, clearAlerts } = useLiveAlerts(locomotiveId);

    const getSensor = (type: SensorType) => sensors.get(type);
    const locoType = health?.locomotive_type ?? sensors.values().next().value?.locomotive_type;

    if (!locomotiveId) {
        return <EmptyDashboard />;
    }

    if (healthLoading && sensors.size === 0) {
        return (
            <Center h="60vh">
                <Stack align="center" gap="md">
                    <Loader size="lg" color="ktzBlue" />
                    <Text size="sm" c="dimmed">Подключение к телеметрии...</Text>
                </Stack>
            </Center>
        );
    }

    // Find latest timestamp from sensors
    const latestTimestamp = Array.from(sensors.values()).reduce<string | null>((latest, s) => {
        if (!latest || s.timestamp > latest) return s.timestamp;
        return latest;
    }, null);

    return (
        <>
            {/* Status strip */}
            <Box className={styles.statusStrip}>
                <Group justify="space-between" px="md" py={6}>
                    <Group gap="md">
                        <Group gap={6}>
                            <IconTrain size={16} style={{ opacity: 0.7 }} />
                            <Text size="sm" fw={600} ff="var(--font-mono), monospace">
                                {locomotiveId.slice(0, 8)}
                            </Text>
                            {locoType && (
                                <Badge
                                    size="xs"
                                    variant="light"
                                    color={locoType === 'TE33A' ? 'ktzGold' : 'ktzCyan'}
                                >
                                    {locoType}
                                </Badge>
                            )}
                        </Group>
                        <ConnectionBadge status={connectionStatus} />
                    </Group>
                    <Group gap="md">
                        {latestTimestamp && (
                            <Group gap={4}>
                                <IconClock size={12} style={{ opacity: 0.5 }} />
                                <Text size="xs" c="dimmed" ff="var(--font-mono), monospace">
                                    {getRelativeTime(latestTimestamp)}
                                </Text>
                            </Group>
                        )}
                        <Group gap={4}>
                            <IconActivity size={12} style={{ opacity: 0.5 }} />
                            <Text size="xs" c="dimmed">
                                {sensors.size} датчиков
                            </Text>
                        </Group>
                    </Group>
                </Group>
            </Box>

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
                    <AlertsPanel alerts={alerts} onClear={clearAlerts} />
                </Box>

                <Box className={styles.trends}>
                    <TrendsPanel locomotiveId={locomotiveId} />
                </Box>

                <Box className={styles.map}>
                    <RouteMap position={position} />
                </Box>
            </Box>
        </>
    );
}
