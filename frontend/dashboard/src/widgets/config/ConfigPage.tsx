'use client';

import { useState } from 'react';
import {
    Alert,
    Badge,
    Box,
    Button,
    Card,
    Group,
    NumberInput,
    Progress,
    Stack,
    Table,
    Tabs,
    Text,
    Title,
    Tooltip,
} from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import {
    IconAlertCircle,
    IconDeviceFloppy,
    IconGauge,
    IconAdjustments,
    IconInfoCircle,
    IconCheck,
} from '@tabler/icons-react';
import {
    useGetThresholdsQuery,
    useUpdateThresholdMutation,
    useGetWeightsQuery,
    useUpdateWeightMutation,
} from '@/features/config';
import { useAppSelector } from '@/store/hooks';
import { selectIsAdmin } from '@/store/authSlice';

const SENSOR_LABELS: Record<string, string> = {
    diesel_rpm: 'Обороты дизеля',
    oil_pressure: 'Давление масла',
    coolant_temp: 'Температура охлаждения',
    fuel_level: 'Уровень топлива',
    fuel_rate: 'Расход топлива',
    traction_motor_temp: 'Темп. тяг. двигателя',
    crankcase_pressure: 'Давление картера',
    catenary_voltage: 'Напряжение контактной сети',
    pantograph_current: 'Ток пантографа',
    transformer_temp: 'Темп. трансформатора',
    igbt_temp: 'Температура IGBT',
    dc_link_voltage: 'Напряжение DC-звена',
    recuperation_current: 'Ток рекуперации',
    speed_actual: 'Скорость фактическая',
    speed_target: 'Скорость заданная',
    brake_pipe_pressure: 'Давл. тормозной магистрали',
    wheel_slip_ratio: 'Коэффициент буксования',
};

const SENSOR_UNITS: Record<string, string> = {
    diesel_rpm: 'об/мин',
    oil_pressure: 'кПа',
    coolant_temp: '°C',
    fuel_level: '%',
    fuel_rate: 'л/ч',
    traction_motor_temp: '°C',
    crankcase_pressure: 'кПа',
    catenary_voltage: 'кВ',
    pantograph_current: 'А',
    transformer_temp: '°C',
    igbt_temp: '°C',
    dc_link_voltage: 'В',
    recuperation_current: 'А',
    speed_actual: 'км/ч',
    speed_target: 'км/ч',
    brake_pipe_pressure: 'кПа',
    wheel_slip_ratio: '%',
};

function ThresholdsTab() {
    const { data: thresholds = [], isLoading } = useGetThresholdsQuery();
    const [updateThreshold] = useUpdateThresholdMutation();
    const [edits, setEdits] = useState<Record<string, { min_value: number; max_value: number }>>(
        {},
    );
    const [saving, setSaving] = useState<Record<string, boolean>>({});

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

    const isModified = (sensorType: string) => !!edits[sensorType];

    const handleSave = async (
        sensorType: string,
        original: { min_value: number; max_value: number },
    ) => {
        const values = edits[sensorType] ?? original;
        if (values.min_value >= values.max_value) {
            showNotification({
                title: 'Ошибка валидации',
                message: 'Минимум должен быть меньше максимума',
                color: 'red',
            });
            return;
        }
        setSaving((prev) => ({ ...prev, [sensorType]: true }));
        try {
            await updateThreshold({
                sensor_type: sensorType,
                min_value: values.min_value,
                max_value: values.max_value,
            }).unwrap();
            showNotification({
                title: 'Сохранено',
                message: `Пороги "${SENSOR_LABELS[sensorType] ?? sensorType}" обновлены`,
                color: 'green',
                icon: <IconCheck size={16} />,
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
        } finally {
            setSaving((prev) => ({ ...prev, [sensorType]: false }));
        }
    };

    const modifiedCount = Object.keys(edits).length;

    return (
        <Stack gap="md">
            {modifiedCount > 0 && (
                <Alert color="ktzGold" variant="light" icon={<IconInfoCircle size={16} />}>
                    Несохранённые изменения: {modifiedCount} датчик(ов). Сохраните каждый отдельно.
                </Alert>
            )}
            <Table striped highlightOnHover verticalSpacing="sm">
                <Table.Thead>
                    <Table.Tr>
                        <Table.Th>Датчик</Table.Th>
                        <Table.Th>Ед.</Table.Th>
                        <Table.Th>Минимум</Table.Th>
                        <Table.Th>Максимум</Table.Th>
                        <Table.Th>Диапазон</Table.Th>
                        <Table.Th>Действие</Table.Th>
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {thresholds.map((t) => {
                        const min = getValue(t.sensor_type, 'min_value', t.min_value);
                        const max = getValue(t.sensor_type, 'max_value', t.max_value);
                        const range = max - min;
                        const modified = isModified(t.sensor_type);

                        return (
                            <Table.Tr
                                key={t.sensor_type}
                                style={modified ? { backgroundColor: 'rgba(254, 198, 4, 0.05)' } : undefined}
                            >
                                <Table.Td>
                                    <Text size="sm" fw={500}>
                                        {SENSOR_LABELS[t.sensor_type] ?? t.sensor_type}
                                    </Text>
                                    <Text size="xs" c="dimmed">
                                        {t.sensor_type}
                                    </Text>
                                </Table.Td>
                                <Table.Td>
                                    <Badge size="xs" variant="outline" color="gray">
                                        {SENSOR_UNITS[t.sensor_type] ?? '—'}
                                    </Badge>
                                </Table.Td>
                                <Table.Td>
                                    <NumberInput
                                        value={min}
                                        onChange={(val) =>
                                            setEdit(t.sensor_type, 'min_value', Number(val), t)
                                        }
                                        size="xs"
                                        w={110}
                                        styles={modified ? { input: { borderColor: 'var(--mantine-color-ktzGold-5)' } } : {}}
                                    />
                                </Table.Td>
                                <Table.Td>
                                    <NumberInput
                                        value={max}
                                        onChange={(val) =>
                                            setEdit(t.sensor_type, 'max_value', Number(val), t)
                                        }
                                        size="xs"
                                        w={110}
                                        styles={modified ? { input: { borderColor: 'var(--mantine-color-ktzGold-5)' } } : {}}
                                    />
                                </Table.Td>
                                <Table.Td>
                                    <Tooltip label={`${min} — ${max} (диапазон: ${range.toFixed(1)})`}>
                                        <Box w={80}>
                                            <Progress
                                                value={100}
                                                color={range > 0 ? 'ktzBlue' : 'critical'}
                                                size="sm"
                                                radius="xl"
                                            />
                                            <Text size="xs" c="dimmed" ta="center">
                                                {range.toFixed(0)}
                                            </Text>
                                        </Box>
                                    </Tooltip>
                                </Table.Td>
                                <Table.Td>
                                    <Button
                                        size="xs"
                                        variant={modified ? 'filled' : 'light'}
                                        color={modified ? 'ktzGold' : 'ktzBlue'}
                                        leftSection={<IconDeviceFloppy size={14} />}
                                        onClick={() => handleSave(t.sensor_type, t)}
                                        loading={saving[t.sensor_type]}
                                        disabled={!modified}
                                    >
                                        Сохранить
                                    </Button>
                                </Table.Td>
                            </Table.Tr>
                        );
                    })}
                    {thresholds.length === 0 && !isLoading && (
                        <Table.Tr>
                            <Table.Td colSpan={6}>
                                <Text ta="center" c="dimmed" size="sm">
                                    Нет данных. Пороги появятся после первого запуска процессора.
                                </Text>
                            </Table.Td>
                        </Table.Tr>
                    )}
                </Table.Tbody>
            </Table>
        </Stack>
    );
}

function WeightsTab() {
    const { data: weights = [], isLoading } = useGetWeightsQuery();
    const [updateWeight] = useUpdateWeightMutation();
    const [edits, setEdits] = useState<Record<string, number>>({});
    const [saving, setSaving] = useState<Record<string, boolean>>({});

    const getValue = (sensorType: string, original: number) => {
        return edits[sensorType] ?? original;
    };

    const isModified = (sensorType: string) => sensorType in edits;

    const handleSave = async (sensorType: string, originalWeight: number) => {
        const weight = edits[sensorType] ?? originalWeight;
        setSaving((prev) => ({ ...prev, [sensorType]: true }));
        try {
            await updateWeight({ sensor_type: sensorType, weight }).unwrap();
            showNotification({
                title: 'Сохранено',
                message: `Вес "${SENSOR_LABELS[sensorType] ?? sensorType}" обновлён`,
                color: 'green',
                icon: <IconCheck size={16} />,
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
        } finally {
            setSaving((prev) => ({ ...prev, [sensorType]: false }));
        }
    };

    const totalWeight = weights.reduce((sum, w) => sum + (edits[w.sensor_type] ?? w.weight), 0);

    return (
        <Stack gap="md">
            <Group gap="md">
                <Card padding="sm" withBorder style={{ flex: 1 }}>
                    <Text size="xs" c="dimmed">Сумма весов</Text>
                    <Text size="lg" fw={700} c={Math.abs(totalWeight - 1) < 0.01 ? 'green' : 'ktzGold'}>
                        {totalWeight.toFixed(3)}
                    </Text>
                    {Math.abs(totalWeight - 1) >= 0.01 && (
                        <Text size="xs" c="ktzGold">
                            Рекомендуется, чтобы сумма равнялась 1.0
                        </Text>
                    )}
                </Card>
            </Group>

            <Table striped highlightOnHover verticalSpacing="sm">
                <Table.Thead>
                    <Table.Tr>
                        <Table.Th>Датчик</Table.Th>
                        <Table.Th>Вес</Table.Th>
                        <Table.Th w={200}>Визуализация</Table.Th>
                        <Table.Th>Действие</Table.Th>
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {weights.map((w) => {
                        const val = getValue(w.sensor_type, w.weight);
                        const modified = isModified(w.sensor_type);

                        return (
                            <Table.Tr
                                key={w.sensor_type}
                                style={modified ? { backgroundColor: 'rgba(254, 198, 4, 0.05)' } : undefined}
                            >
                                <Table.Td>
                                    <Text size="sm" fw={500}>
                                        {SENSOR_LABELS[w.sensor_type] ?? w.sensor_type}
                                    </Text>
                                    <Text size="xs" c="dimmed">
                                        {w.sensor_type}
                                    </Text>
                                </Table.Td>
                                <Table.Td>
                                    <NumberInput
                                        value={val}
                                        onChange={(v) =>
                                            setEdits((prev) => ({ ...prev, [w.sensor_type]: Number(v) }))
                                        }
                                        min={0}
                                        max={1}
                                        step={0.01}
                                        decimalScale={3}
                                        size="xs"
                                        w={100}
                                        styles={modified ? { input: { borderColor: 'var(--mantine-color-ktzGold-5)' } } : {}}
                                    />
                                </Table.Td>
                                <Table.Td>
                                    <Progress
                                        value={val * 100}
                                        color={val > 0.15 ? 'critical' : val > 0.08 ? 'ktzGold' : 'ktzBlue'}
                                        size="lg"
                                        radius="xl"
                                    />
                                </Table.Td>
                                <Table.Td>
                                    <Button
                                        size="xs"
                                        variant={modified ? 'filled' : 'light'}
                                        color={modified ? 'ktzGold' : 'ktzBlue'}
                                        leftSection={<IconDeviceFloppy size={14} />}
                                        onClick={() => handleSave(w.sensor_type, w.weight)}
                                        loading={saving[w.sensor_type]}
                                        disabled={!modified}
                                    >
                                        Сохранить
                                    </Button>
                                </Table.Td>
                            </Table.Tr>
                        );
                    })}
                    {weights.length === 0 && !isLoading && (
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
        </Stack>
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
                Только администраторы могут изменять настройки. Текущая роль не имеет прав на редактирование конфигурации.
            </Alert>
        );
    }

    return (
        <Stack gap="lg">
            <Group justify="space-between">
                <Title order={3}>Настройки индекса здоровья</Title>
                <Badge color="ktzGold" variant="light" size="lg">
                    Администратор
                </Badge>
            </Group>

            <Card padding="lg" withBorder>
                <Tabs defaultValue="thresholds">
                    <Tabs.List>
                        <Tabs.Tab value="thresholds" leftSection={<IconGauge size={16} />}>
                            Пороговые значения
                        </Tabs.Tab>
                        <Tabs.Tab value="weights" leftSection={<IconAdjustments size={16} />}>
                            Веса параметров
                        </Tabs.Tab>
                    </Tabs.List>

                    <Tabs.Panel value="thresholds" pt="md">
                        <Text size="sm" c="dimmed" mb="md">
                            Настройте минимальные и максимальные допустимые значения для каждого датчика.
                            Выход за пределы порогов влияет на расчёт индекса здоровья.
                        </Text>
                        <ThresholdsTab />
                    </Tabs.Panel>

                    <Tabs.Panel value="weights" pt="md">
                        <Text size="sm" c="dimmed" mb="md">
                            Настройте весовые коэффициенты вклада каждого датчика в общий индекс здоровья.
                            Более высокий вес означает большее влияние на итоговый показатель.
                        </Text>
                        <WeightsTab />
                    </Tabs.Panel>
                </Tabs>
            </Card>
        </Stack>
    );
}
