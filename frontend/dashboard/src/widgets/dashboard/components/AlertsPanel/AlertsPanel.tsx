'use client';

import { useState, useEffect, useRef } from 'react';
import {
    Card,
    Text,
    Group,
    Badge,
    Button,
    ScrollArea,
    Stack,
    ActionIcon,
    SegmentedControl,
    Transition,
    Tooltip,
    ThemeIcon,
} from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import {
    IconCheck,
    IconAlertTriangle,
    IconAlertCircle,
    IconInfoCircle,
    IconBell,
    IconBellOff,
} from '@tabler/icons-react';
import type { AlertEvent } from '@/features/alerts/types';
import { useAcknowledgeAlertMutation } from '@/features/alerts';
import { getRelativeTime } from '@/shared/utils/date';
import classes from './AlertsPanel.module.css';

interface AlertsPanelProps {
    alerts: AlertEvent[];
    onClear: () => void;
    isReplay?: boolean;
}

type SeverityFilter = 'all' | 'emergency' | 'critical' | 'warning' | 'info';

const severityClassMap: Record<string, string> = {
    info: classes.severityInfo,
    warning: classes.severityWarning,
    critical: classes.severityCritical,
    emergency: classes.severityEmergency,
};

const severityIcons: Record<string, typeof IconInfoCircle> = {
    info: IconInfoCircle,
    warning: IconAlertTriangle,
    critical: IconAlertCircle,
    emergency: IconAlertCircle,
};

const severityColors: Record<string, string> = {
    info: 'ktzBlue',
    warning: 'ktzGold',
    critical: 'critical',
    emergency: 'critical',
};

const severityLabels: Record<string, string> = {
    info: 'Инфо',
    warning: 'Внимание',
    critical: 'Критич.',
    emergency: 'Авария',
};

function AlertItem({ alert, isNew }: { alert: AlertEvent; isNew: boolean }) {
    const [acknowledge, { isLoading }] = useAcknowledgeAlertMutation();
    const isEmergency = alert.severity === 'emergency';
    const isCritical = alert.severity === 'critical';
    const SeverityIcon = severityIcons[alert.severity] ?? IconInfoCircle;

    return (
        <Transition mounted={true} transition="slide-right" duration={300}>
            {(style) => (
                <div
                    className={`${classes.alertItem} ${isEmergency ? classes.alertEmergency : ''} ${isNew ? classes.alertNew : ''}`}
                    style={style}
                >
                    <div
                        className={`${classes.severityStripe} ${severityClassMap[alert.severity] ?? ''}`}
                    />
                    <ThemeIcon
                        variant="light"
                        color={severityColors[alert.severity]}
                        size="sm"
                        className={isEmergency || isCritical ? classes.iconPulse : ''}
                    >
                        <SeverityIcon size={14} />
                    </ThemeIcon>
                    <div className={classes.alertContent}>
                        <Stack gap={2}>
                            <Text
                                size="sm"
                                lineClamp={2}
                                fw={isCritical || isEmergency ? 600 : 400}
                            >
                                {alert.message}
                            </Text>
                            <Group gap="xs">
                                <Badge
                                    size="xs"
                                    variant="light"
                                    color={severityColors[alert.severity]}
                                >
                                    {severityLabels[alert.severity] ?? alert.severity}
                                </Badge>
                                <Badge size="xs" variant="outline" color="gray">
                                    {alert.sensor_type}
                                </Badge>
                                <Text size="xs" c="dimmed">
                                    {getRelativeTime(alert.timestamp)}
                                </Text>
                            </Group>
                        </Stack>
                    </div>
                    <div className={classes.alertAction}>
                        {!alert.acknowledged ? (
                            <Tooltip label="Подтвердить">
                                <ActionIcon
                                    variant="subtle"
                                    size="sm"
                                    color="green"
                                    loading={isLoading}
                                    onClick={() => acknowledge(alert.id)}
                                    aria-label="Подтвердить"
                                >
                                    <IconCheck size={16} />
                                </ActionIcon>
                            </Tooltip>
                        ) : (
                            <Tooltip label="Подтверждено">
                                <IconCheck
                                    size={16}
                                    style={{ opacity: 0.35, color: 'var(--mantine-color-green-5)' }}
                                />
                            </Tooltip>
                        )}
                    </div>
                </div>
            )}
        </Transition>
    );
}

export default function AlertsPanel({ alerts, onClear, isReplay }: AlertsPanelProps) {
    const [filter, setFilter] = useState<SeverityFilter>('all');
    const [soundEnabled, setSoundEnabled] = useState(true);
    const prevCountRef = useRef(alerts.length);

    // Show notification for new critical/emergency alerts (only in live mode)
    useEffect(() => {
        if (isReplay) return;
        if (alerts.length > prevCountRef.current) {
            const newAlerts = alerts.slice(0, alerts.length - prevCountRef.current);
            for (const alert of newAlerts) {
                if (alert.severity === 'critical' || alert.severity === 'emergency') {
                    showNotification({
                        title: alert.severity === 'emergency' ? 'АВАРИЯ' : 'Критическое оповещение',
                        message: alert.message,
                        color: 'red',
                        autoClose: alert.severity === 'emergency' ? false : 8000,
                        icon: <IconAlertCircle size={18} />,
                    });

                    if (soundEnabled) {
                        try {
                            const ctx = new AudioContext();
                            const osc = ctx.createOscillator();
                            const gain = ctx.createGain();
                            osc.connect(gain);
                            gain.connect(ctx.destination);
                            osc.frequency.value = alert.severity === 'emergency' ? 880 : 660;
                            gain.gain.value = 0.15;
                            osc.start();
                            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
                            osc.stop(ctx.currentTime + 0.5);
                        } catch {
                            // audio not available
                        }
                    }
                }
            }
        }
        prevCountRef.current = alerts.length;
    }, [alerts, soundEnabled, isReplay]);

    const filteredAlerts = filter === 'all' ? alerts : alerts.filter((a) => a.severity === filter);

    const counts = {
        emergency: alerts.filter((a) => a.severity === 'emergency').length,
        critical: alerts.filter((a) => a.severity === 'critical').length,
        warning: alerts.filter((a) => a.severity === 'warning').length,
        info: alerts.filter((a) => a.severity === 'info').length,
    };
    const unacknowledgedCount = alerts.filter((a) => !a.acknowledged).length;
    const newAlertIds = new Set(alerts.slice(0, 3).map((a) => a.id));

    const acknowledgedCount = alerts.filter((a) => a.acknowledged).length;

    return (
        <Card
            style={{
                borderTop: `2px solid var(--mantine-color-${isReplay ? 'ktzGold' : 'critical'}-5)`,
            }}
        >
            <Group justify="space-between" mb="xs">
                <Group gap="xs">
                    <Text className="panel-label">ОПОВЕЩЕНИЯ</Text>
                    {isReplay && (
                        <Badge size="xs" variant="light" color="ktzGold">
                            REPLAY
                        </Badge>
                    )}
                    {unacknowledgedCount > 0 && (
                        <Badge
                            size="sm"
                            color="red"
                            variant="filled"
                            className={!isReplay && unacknowledgedCount > 0 ? 'led-pulse' : ''}
                        >
                            {unacknowledgedCount}
                        </Badge>
                    )}
                    {isReplay && acknowledgedCount > 0 && (
                        <Badge size="xs" variant="light" color="green">
                            {acknowledgedCount} подтв.
                        </Badge>
                    )}
                </Group>
                <Group gap={4}>
                    {!isReplay && (
                        <>
                            <Tooltip label={soundEnabled ? 'Выкл. звук' : 'Вкл. звук'}>
                                <ActionIcon
                                    variant="subtle"
                                    size="sm"
                                    color={soundEnabled ? 'ktzBlue' : 'gray'}
                                    onClick={() => setSoundEnabled(!soundEnabled)}
                                >
                                    {soundEnabled ? (
                                        <IconBell size={14} />
                                    ) : (
                                        <IconBellOff size={14} />
                                    )}
                                </ActionIcon>
                            </Tooltip>
                            <Button variant="subtle" size="xs" onClick={onClear}>
                                Очистить
                            </Button>
                        </>
                    )}
                </Group>
            </Group>

            {/* Severity summary counters */}
            <Group gap="xs" mb="xs">
                {counts.emergency > 0 && (
                    <Badge
                        color="red"
                        variant="filled"
                        size="xs"
                        leftSection={<IconAlertCircle size={10} />}
                    >
                        {counts.emergency}
                    </Badge>
                )}
                {counts.critical > 0 && (
                    <Badge
                        color="critical"
                        variant="light"
                        size="xs"
                        leftSection={<IconAlertCircle size={10} />}
                    >
                        {counts.critical}
                    </Badge>
                )}
                {counts.warning > 0 && (
                    <Badge
                        color="ktzGold"
                        variant="light"
                        size="xs"
                        leftSection={<IconAlertTriangle size={10} />}
                    >
                        {counts.warning}
                    </Badge>
                )}
                {counts.info > 0 && (
                    <Badge
                        color="ktzBlue"
                        variant="light"
                        size="xs"
                        leftSection={<IconInfoCircle size={10} />}
                    >
                        {counts.info}
                    </Badge>
                )}
            </Group>

            {/* Severity filter */}
            <SegmentedControl
                size="xs"
                value={filter}
                onChange={(v) => setFilter(v as SeverityFilter)}
                data={[
                    { label: `Все (${alerts.length})`, value: 'all' },
                    { label: `Авария (${counts.emergency})`, value: 'emergency' },
                    { label: `Крит. (${counts.critical})`, value: 'critical' },
                    { label: `Вним. (${counts.warning})`, value: 'warning' },
                ]}
                mb="sm"
                fullWidth
            />

            {filteredAlerts.length === 0 ? (
                <Text c="dimmed" ta="center" py="xl">
                    {filter === 'all'
                        ? 'Нет оповещений'
                        : `Нет оповещений уровня "${severityLabels[filter]}"`}
                </Text>
            ) : (
                <ScrollArea.Autosize mah={350}>
                    {filteredAlerts.map((alert) => (
                        <AlertItem key={alert.id} alert={alert} isNew={newAlertIds.has(alert.id)} />
                    ))}
                </ScrollArea.Autosize>
            )}
        </Card>
    );
}
