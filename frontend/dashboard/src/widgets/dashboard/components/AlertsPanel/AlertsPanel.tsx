'use client';

import { Card, Text, Group, Badge, Button, ScrollArea, Stack, ActionIcon } from '@mantine/core';
import { IconCheck } from '@tabler/icons-react';
import type { AlertEvent } from '@/features/alerts/types';
import { useAcknowledgeAlertMutation } from '@/features/alerts';
import { getRelativeTime } from '@/shared/utils/date';
import classes from './AlertsPanel.module.css';

interface AlertsPanelProps {
    alerts: AlertEvent[];
    onClear: () => void;
}

const severityClassMap: Record<string, string> = {
    info: classes.severityInfo,
    warning: classes.severityWarning,
    critical: classes.severityCritical,
    emergency: classes.severityEmergency,
};

function AlertItem({ alert }: { alert: AlertEvent }) {
    const [acknowledge, { isLoading }] = useAcknowledgeAlertMutation();
    const isEmergency = alert.severity === 'emergency';

    return (
        <div className={`${classes.alertItem} ${isEmergency ? classes.alertEmergency : ''}`}>
            <div
                className={`${classes.severityStripe} ${severityClassMap[alert.severity] ?? ''}`}
            />
            <div className={classes.alertContent}>
                <Stack gap={2}>
                    <Text size="sm" lineClamp={2}>
                        {alert.message}
                    </Text>
                    <Group gap="xs">
                        <Badge size="xs" variant="light">
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
                ) : (
                    <IconCheck size={16} style={{ opacity: 0.35 }} />
                )}
            </div>
        </div>
    );
}

export default function AlertsPanel({ alerts, onClear }: AlertsPanelProps) {
    const unacknowledgedCount = alerts.filter((a) => !a.acknowledged).length;

    return (
        <Card style={{ borderTop: '2px solid var(--mantine-color-critical-5)' }}>
            <Group justify="space-between" mb="sm">
                <Group gap="xs">
                    <Text className="panel-label">ОПОВЕЩЕНИЯ</Text>
                    {unacknowledgedCount > 0 && (
                        <Badge size="sm" color="red" variant="filled">
                            {unacknowledgedCount}
                        </Badge>
                    )}
                </Group>
                <Button variant="subtle" size="xs" onClick={onClear}>
                    Очистить
                </Button>
            </Group>

            {alerts.length === 0 ? (
                <Text c="dimmed" ta="center" py="xl">
                    Нет оповещений
                </Text>
            ) : (
                <ScrollArea.Autosize mah={300}>
                    {alerts.map((alert) => (
                        <AlertItem key={alert.id} alert={alert} />
                    ))}
                </ScrollArea.Autosize>
            )}
        </Card>
    );
}
