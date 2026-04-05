'use client';

import {useState} from 'react';
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
    Tooltip,
    ThemeIcon,
} from '@mantine/core';
import {IconCheck, IconAlertTriangle, IconAlertCircle, IconInfoCircle} from '@tabler/icons-react';
import type {AlertEvent} from '@/features/alerts/types';
import {useAcknowledgeAlertMutation} from '@/features/alerts';
import {getRelativeTime} from '@/shared/utils/date';
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

function AlertItem({
                       alert,
                       onAcknowledged,
                   }: {
    alert: AlertEvent;
    onAcknowledged?: (id: string) => void;
}) {
    const [acknowledge, {isLoading}] = useAcknowledgeAlertMutation();
    const [acked, setAcked] = useState(alert.acknowledged);
    const isEmergency = alert.severity === 'emergency';
    const isCritical = alert.severity === 'critical';
    const SeverityIcon = severityIcons[alert.severity] ?? IconInfoCircle;

    const handleAck = async () => {
        try {
            await acknowledge(alert.id).unwrap();
            setAcked(true);
            onAcknowledged?.(alert.id);
        } catch {
        }
    };

    return (
        <div
            className={`${classes.alertItem} ${isEmergency && !acked ? classes.alertEmergency : ''} ${acked ? classes.alertAcknowledged : ''}`}
        >
            <div
                className={`${classes.severityStripe} ${severityClassMap[alert.severity] ?? ''}`}
            />
            <ThemeIcon
                variant="light"
                color={acked ? 'gray' : severityColors[alert.severity]}
                size="sm"
                className={!acked && (isEmergency || isCritical) ? classes.iconPulse : ''}
            >
                <SeverityIcon size={14}/>
            </ThemeIcon>
            <div className={classes.alertContent}>
                <Stack gap={2}>
                    <Text
                        size="sm"
                        lineClamp={2}
                        fw={!acked && (isCritical || isEmergency) ? 600 : 400}
                        c={acked ? 'dimmed' : undefined}
                    >
                        {alert.message}
                    </Text>
                    <Group gap="xs">
                        <Badge
                            size="xs"
                            variant="light"
                            color={acked ? 'gray' : severityColors[alert.severity]}
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
                {!acked ? (
                    <Tooltip label="Подтвердить">
                        <ActionIcon
                            variant="light"
                            size="sm"
                            color="green"
                            loading={isLoading}
                            onClick={handleAck}
                            aria-label="Подтвердить"
                        >
                            <IconCheck size={14}/>
                        </ActionIcon>
                    </Tooltip>
                ) : (
                    <Badge size="xs" variant="filled" color="green" radius="xl">
                        <IconCheck size={10}/>
                    </Badge>
                )}
            </div>
        </div>
    );
}

export default function AlertsPanel({alerts, onClear, isReplay}: AlertsPanelProps) {
    const [filter, setFilter] = useState<SeverityFilter>('all');
    const [localAcked, setLocalAcked] = useState<Set<string>>(new Set());

    const handleAcknowledged = (id: string) => {
        setLocalAcked((prev) => new Set(prev).add(id));
    };

    // Overlay local acknowledgements on top of server-provided alert data
    const mergedAlerts = alerts.map((a) =>
        localAcked.has(a.id) ? {...a, acknowledged: true} : a,
    );

    const filteredAlerts =
        filter === 'all' ? mergedAlerts : mergedAlerts.filter((a) => a.severity === filter);

    const counts = {
        emergency: mergedAlerts.filter((a) => a.severity === 'emergency').length,
        critical: mergedAlerts.filter((a) => a.severity === 'critical').length,
        warning: mergedAlerts.filter((a) => a.severity === 'warning').length,
        info: mergedAlerts.filter((a) => a.severity === 'info').length,
    };
    const unacknowledgedCount = mergedAlerts.filter((a) => !a.acknowledged).length;
    const acknowledgedCount = mergedAlerts.filter((a) => a.acknowledged).length;

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
                            className={!isReplay ? 'led-pulse' : ''}
                        >
                            {unacknowledgedCount}
                        </Badge>
                    )}
                    {acknowledgedCount > 0 && (
                        <Badge size="xs" variant="light" color="green">
                            {acknowledgedCount} подтв.
                        </Badge>
                    )}
                </Group>
                {!isReplay && (
                    <Button variant="subtle" size="xs" onClick={onClear}>
                        Очистить
                    </Button>
                )}
            </Group>

            {mergedAlerts.length > 0 && (
                <Group gap="xs" mb="xs">
                    {counts.emergency > 0 && (
                        <Badge color="red" variant="filled" size="xs">
                            {counts.emergency} авар.
                        </Badge>
                    )}
                    {counts.critical > 0 && (
                        <Badge color="critical" variant="light" size="xs">
                            {counts.critical} крит.
                        </Badge>
                    )}
                    {counts.warning > 0 && (
                        <Badge color="ktzGold" variant="light" size="xs">
                            {counts.warning} вним.
                        </Badge>
                    )}
                    {counts.info > 0 && (
                        <Badge color="ktzBlue" variant="light" size="xs">
                            {counts.info} инфо
                        </Badge>
                    )}
                </Group>
            )}

            {mergedAlerts.length > 3 && (
                <SegmentedControl
                    size="xs"
                    value={filter}
                    onChange={(v) => setFilter(v as SeverityFilter)}
                    data={[
                        {label: `Все (${mergedAlerts.length})`, value: 'all'},
                        {label: `Авария (${counts.emergency})`, value: 'emergency'},
                        {label: `Крит. (${counts.critical})`, value: 'critical'},
                        {label: `Вним. (${counts.warning})`, value: 'warning'},
                    ]}
                    mb="sm"
                    fullWidth
                />
            )}

            {filteredAlerts.length === 0 ? (
                <Text c="dimmed" ta="center" py="xl">
                    {mergedAlerts.length === 0
                        ? 'Нет оповещений'
                        : `Нет оповещений уровня "${severityLabels[filter]}"`}
                </Text>
            ) : (
                <ScrollArea.Autosize mah={350}>
                    {filteredAlerts.map((alert) => (
                        <AlertItem
                            key={alert.id}
                            alert={alert}
                            onAcknowledged={handleAcknowledged}
                        />
                    ))}
                </ScrollArea.Autosize>
            )}
        </Card>
    );
}
