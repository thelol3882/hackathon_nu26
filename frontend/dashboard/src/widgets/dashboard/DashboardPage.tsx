'use client';

import { Box, Text, Center, Loader } from '@mantine/core';
import { useLocomotive } from '@/widgets/layout/LocomotiveContext';
import { useLiveTelemetry } from '@/features/telemetry';
import { useHealthIndex } from '@/features/health';
import { useLiveAlerts } from '@/features/alerts';
import type { SensorType } from '@/features/telemetry/types';

import { HealthIndexGauge } from './components/HealthIndexGauge/HealthIndexGauge';
import SpeedPanel from './components/SpeedPanel/SpeedPanel';
import FuelEnergyPanel from './components/FuelEnergyPanel/FuelEnergyPanel';
import PressureTemperaturePanel from './components/PressureTemperaturePanel/PressureTemperaturePanel';
import ElectricalPanel from './components/ElectricalPanel/ElectricalPanel';
import AlertsPanel from './components/AlertsPanel/AlertsPanel';
import TrendsPanel from './components/TrendsPanel/TrendsPanel';
import { RouteMap } from './components/RouteMap/RouteMap';

import styles from './DashboardPage.module.css';

export function DashboardPage() {
    const { locomotiveId } = useLocomotive();
    const { sensors, position } = useLiveTelemetry(locomotiveId);
    const { health, isLoading: healthLoading } = useHealthIndex(locomotiveId);
    const { alerts, clearAlerts } = useLiveAlerts(locomotiveId);

    const getSensor = (type: SensorType) => sensors.get(type);
    const locoType = health?.locomotive_type;

    if (!locomotiveId) {
        return (
            <Center h="60vh">
                <Text size="lg" c="var(--dashboard-text-secondary)">
                    Выберите локомотив для мониторинга
                </Text>
            </Center>
        );
    }

    if (healthLoading && sensors.size === 0) {
        return (
            <Center h="60vh">
                <Loader size="lg" />
            </Center>
        );
    }

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
                <AlertsPanel alerts={alerts} onClear={clearAlerts} />
            </Box>

            <Box className={styles.trends}>
                <TrendsPanel locomotiveId={locomotiveId} />
            </Box>

            <Box className={styles.map}>
                <RouteMap position={position} />
            </Box>
        </Box>
    );
}
