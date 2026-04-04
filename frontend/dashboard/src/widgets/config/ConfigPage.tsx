'use client';

import { useState } from 'react';
import { Alert, Button, Card, NumberInput, Stack, Table, Tabs, Text, Title } from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import { IconAlertCircle, IconDeviceFloppy } from '@tabler/icons-react';
import {
    useGetThresholdsQuery,
    useUpdateThresholdMutation,
    useGetWeightsQuery,
    useUpdateWeightMutation,
} from '@/features/config';
import { useAppSelector } from '@/store/hooks';
import { selectIsAdmin } from '@/store/authSlice';

function ThresholdsTab() {
    const { data: thresholds = [] } = useGetThresholdsQuery();
    const [updateThreshold] = useUpdateThresholdMutation();
    const [edits, setEdits] = useState<Record<string, { min_value: number; max_value: number }>>(
        {},
    );

    const getValue = (sensorType: string, field: 'min_value' | 'max_value', original: number) => {
        return edits[sensorType]?.[field] ?? original;
    };

    const setEdit = (
        sensorType: string,
        field: 'min_value' | 'max_value',
        value: number,
        original: { min_value: number; max_value: number },
    ) => {
        setEdits((prev) => ({
            ...prev,
            [sensorType]: {
                min_value: prev[sensorType]?.min_value ?? original.min_value,
                max_value: prev[sensorType]?.max_value ?? original.max_value,
                [field]: value,
            },
        }));
    };

    const handleSave = async (
        sensorType: string,
        original: { min_value: number; max_value: number },
    ) => {
        const values = edits[sensorType] ?? original;
        try {
            await updateThreshold({
                sensor_type: sensorType,
                min_value: values.min_value,
                max_value: values.max_value,
            }).unwrap();
            showNotification({
                title: 'Сохранено',
                message: `Пороги для "${sensorType}" обновлены`,
                color: 'green',
            });
            setEdits((prev) => {
                const next = { ...prev };
                delete next[sensorType];
                return next;
            });
        } catch {
            showNotification({
                title: 'Ошибка',
                message: `Не удалось обновить пороги для "${sensorType}"`,
                color: 'red',
            });
        }
    };

    return (
        <Table striped highlightOnHover>
            <Table.Thead>
                <Table.Tr>
                    <Table.Th>Тип датчика</Table.Th>
                    <Table.Th>Минимум</Table.Th>
                    <Table.Th>Максимум</Table.Th>
                    <Table.Th>Действие</Table.Th>
                </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
                {thresholds.map((t) => (
                    <Table.Tr key={t.sensor_type}>
                        <Table.Td>{t.sensor_type}</Table.Td>
                        <Table.Td>
                            <NumberInput
                                value={getValue(t.sensor_type, 'min_value', t.min_value)}
                                onChange={(val) =>
                                    setEdit(t.sensor_type, 'min_value', Number(val), t)
                                }
                                size="xs"
                                w={120}
                            />
                        </Table.Td>
                        <Table.Td>
                            <NumberInput
                                value={getValue(t.sensor_type, 'max_value', t.max_value)}
                                onChange={(val) =>
                                    setEdit(t.sensor_type, 'max_value', Number(val), t)
                                }
                                size="xs"
                                w={120}
                            />
                        </Table.Td>
                        <Table.Td>
                            <Button
                                size="xs"
                                variant="light"
                                leftSection={<IconDeviceFloppy size={14} />}
                                onClick={() => handleSave(t.sensor_type, t)}
                            >
                                Сохранить
                            </Button>
                        </Table.Td>
                    </Table.Tr>
                ))}
                {thresholds.length === 0 && (
                    <Table.Tr>
                        <Table.Td colSpan={4}>
                            <Text ta="center" c="dimmed" size="sm">
                                Нет данных
                            </Text>
                        </Table.Td>
                    </Table.Tr>
                )}
            </Table.Tbody>
        </Table>
    );
}

function WeightsTab() {
    const { data: weights = [] } = useGetWeightsQuery();
    const [updateWeight] = useUpdateWeightMutation();
    const [edits, setEdits] = useState<Record<string, number>>({});

    const getValue = (sensorType: string, original: number) => {
        return edits[sensorType] ?? original;
    };

    const handleSave = async (sensorType: string, originalWeight: number) => {
        const weight = edits[sensorType] ?? originalWeight;
        try {
            await updateWeight({ sensor_type: sensorType, weight }).unwrap();
            showNotification({
                title: 'Сохранено',
                message: `Вес для "${sensorType}" обновлён`,
                color: 'green',
            });
            setEdits((prev) => {
                const next = { ...prev };
                delete next[sensorType];
                return next;
            });
        } catch {
            showNotification({
                title: 'Ошибка',
                message: `Не удалось обновить вес для "${sensorType}"`,
                color: 'red',
            });
        }
    };

    return (
        <Table striped highlightOnHover>
            <Table.Thead>
                <Table.Tr>
                    <Table.Th>Тип датчика</Table.Th>
                    <Table.Th>Вес</Table.Th>
                    <Table.Th>Действие</Table.Th>
                </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
                {weights.map((w) => (
                    <Table.Tr key={w.sensor_type}>
                        <Table.Td>{w.sensor_type}</Table.Td>
                        <Table.Td>
                            <NumberInput
                                value={getValue(w.sensor_type, w.weight)}
                                onChange={(val) =>
                                    setEdits((prev) => ({ ...prev, [w.sensor_type]: Number(val) }))
                                }
                                min={0}
                                max={1}
                                step={0.01}
                                decimalScale={2}
                                size="xs"
                                w={120}
                            />
                        </Table.Td>
                        <Table.Td>
                            <Button
                                size="xs"
                                variant="light"
                                leftSection={<IconDeviceFloppy size={14} />}
                                onClick={() => handleSave(w.sensor_type, w.weight)}
                            >
                                Сохранить
                            </Button>
                        </Table.Td>
                    </Table.Tr>
                ))}
                {weights.length === 0 && (
                    <Table.Tr>
                        <Table.Td colSpan={3}>
                            <Text ta="center" c="dimmed" size="sm">
                                Нет данных
                            </Text>
                        </Table.Td>
                    </Table.Tr>
                )}
            </Table.Tbody>
        </Table>
    );
}

export function ConfigPage() {
    const isAdmin = useAppSelector(selectIsAdmin);

    if (!isAdmin) {
        return (
            <Alert
                color="red"
                variant="light"
                icon={<IconAlertCircle size={16} />}
                title="Доступ запрещён"
            >
                Только администраторы могут изменять настройки.
            </Alert>
        );
    }

    return (
        <Stack gap="lg">
            <Title order={3}>Настройки</Title>

            <Card padding="lg" withBorder>
                <Tabs defaultValue="thresholds">
                    <Tabs.List>
                        <Tabs.Tab value="thresholds">Пороги</Tabs.Tab>
                        <Tabs.Tab value="weights">Веса</Tabs.Tab>
                    </Tabs.List>

                    <Tabs.Panel value="thresholds" pt="md">
                        <ThresholdsTab />
                    </Tabs.Panel>

                    <Tabs.Panel value="weights" pt="md">
                        <WeightsTab />
                    </Tabs.Panel>
                </Tabs>
            </Card>
        </Stack>
    );
}
