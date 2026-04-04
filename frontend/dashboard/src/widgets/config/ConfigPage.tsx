'use client';

import { useState } from 'react';
import {
    Alert,
    Badge,
    Box,
    Button,
    Card,
    Center,
    Group,
    NumberInput,
    Progress,
    Stack,
    Table,
    Tabs,
    Text,
    ThemeIcon,
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
    IconUsers,
    IconShieldCheck,
    IconUser,
} from '@tabler/icons-react';
import {
    useGetThresholdsQuery,
    useUpdateThresholdMutation,
    useGetWeightsQuery,
    useUpdateWeightMutation,
} from '@/features/config';
import { useGetUsersQuery } from '@/features/auth';
import { useAppSelector } from '@/store/hooks';
import { selectIsAdmin } from '@/store/authSlice';
import { formatDateTime } from '@/shared/utils/date';

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
    const [edits, setEdits] = useState<Record<string, { min_value: number; max_value: number }>>({});
    const [saving, setSaving] = useState<Record<string, boolean>>({});

    const getValue = (sensorType: string, field: 'min_value' | 'max_value', original: number) =>
        edits[sensorType]?.[field] ?? original;

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

    const handleSave = async (sensorType: string, original: { min_value: number; max_value: number }) => {
        const values = edits[sensorType] ?? original;
        if (values.min_value >= values.max_value) {
            showNotification({ title: 'Ошибка', message: 'Минимум должен быть меньше максимума', color: 'red' });
            return;
        }
        setSaving((p) => ({ ...p, [sensorType]: true }));
        try {
            await updateThreshold({ sensor_type: sensorType, min_value: values.min_value, max_value: values.max_value }).unwrap();
            showNotification({ title: 'Сохранено', message: `Пороги «${SENSOR_LABELS[sensorType] ?? sensorType}» обновлены`, color: 'green', icon: <IconCheck size={16} /> });
            setEdits((p) => { const n = { ...p }; delete n[sensorType]; return n; });
        } catch {
            showNotification({ title: 'Ошибка', message: 'Не удалось сохранить', color: 'red' });
        } finally {
            setSaving((p) => ({ ...p, [sensorType]: false }));
        }
    };

    const modifiedCount = Object.keys(edits).length;

    return (
        <Stack gap="md">
            {modifiedCount > 0 && (
                <Alert color="ktzGold" variant="light" icon={<IconInfoCircle size={16} />}>
                    {modifiedCount} несохр. изменений
                </Alert>
            )}
            <Table striped highlightOnHover verticalSpacing="xs">
                <Table.Thead>
                    <Table.Tr>
                        <Table.Th>Датчик</Table.Th>
                        <Table.Th>Ед.</Table.Th>
                        <Table.Th>Минимум</Table.Th>
                        <Table.Th>Максимум</Table.Th>
                        <Table.Th>Диапазон</Table.Th>
                        <Table.Th />
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {thresholds.map((t) => {
                        const min = getValue(t.sensor_type, 'min_value', t.min_value);
                        const max = getValue(t.sensor_type, 'max_value', t.max_value);
                        const modified = !!edits[t.sensor_type];
                        return (
                            <Table.Tr key={t.sensor_type} style={modified ? { backgroundColor: 'rgba(254,198,4,0.04)' } : undefined}>
                                <Table.Td>
                                    <Text size="sm" fw={500}>{SENSOR_LABELS[t.sensor_type] ?? t.sensor_type}</Text>
                                    <Text size="xs" c="dimmed" ff="var(--font-mono), monospace">{t.sensor_type}</Text>
                                </Table.Td>
                                <Table.Td><Badge size="xs" variant="outline" color="gray">{SENSOR_UNITS[t.sensor_type] ?? '—'}</Badge></Table.Td>
                                <Table.Td>
                                    <NumberInput value={min} onChange={(v) => setEdit(t.sensor_type, 'min_value', Number(v), t)} size="xs" w={100} styles={modified ? { input: { borderColor: 'var(--mantine-color-ktzGold-5)' } } : {}} />
                                </Table.Td>
                                <Table.Td>
                                    <NumberInput value={max} onChange={(v) => setEdit(t.sensor_type, 'max_value', Number(v), t)} size="xs" w={100} styles={modified ? { input: { borderColor: 'var(--mantine-color-ktzGold-5)' } } : {}} />
                                </Table.Td>
                                <Table.Td>
                                    <Tooltip label={`${min} — ${max}`}>
                                        <Box w={70}>
                                            <Progress value={100} color={max - min > 0 ? 'ktzBlue' : 'critical'} size="xs" radius="xl" />
                                            <Text size="xs" c="dimmed" ta="center">{(max - min).toFixed(0)}</Text>
                                        </Box>
                                    </Tooltip>
                                </Table.Td>
                                <Table.Td>
                                    <Button size="xs" variant={modified ? 'filled' : 'subtle'} color={modified ? 'ktzGold' : 'gray'} leftSection={<IconDeviceFloppy size={14} />} onClick={() => handleSave(t.sensor_type, t)} loading={saving[t.sensor_type]} disabled={!modified}>
                                        Сохранить
                                    </Button>
                                </Table.Td>
                            </Table.Tr>
                        );
                    })}
                    {thresholds.length === 0 && !isLoading && (
                        <Table.Tr><Table.Td colSpan={6}><Text ta="center" c="dimmed" size="sm">Нет данных</Text></Table.Td></Table.Tr>
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

    const getValue = (s: string, orig: number) => edits[s] ?? orig;

    const handleSave = async (sensorType: string, originalWeight: number) => {
        const weight = edits[sensorType] ?? originalWeight;
        setSaving((p) => ({ ...p, [sensorType]: true }));
        try {
            await updateWeight({ sensor_type: sensorType, weight }).unwrap();
            showNotification({ title: 'Сохранено', message: `Вес «${SENSOR_LABELS[sensorType] ?? sensorType}» обновлён`, color: 'green', icon: <IconCheck size={16} /> });
            setEdits((p) => { const n = { ...p }; delete n[sensorType]; return n; });
        } catch {
            showNotification({ title: 'Ошибка', message: 'Не удалось сохранить', color: 'red' });
        } finally {
            setSaving((p) => ({ ...p, [sensorType]: false }));
        }
    };

    const totalWeight = weights.reduce((sum, w) => sum + (edits[w.sensor_type] ?? w.weight), 0);
    const sumOk = Math.abs(totalWeight - 1) < 0.01;

    return (
        <Stack gap="md">
            <Card padding="xs" withBorder>
                <Group gap="md">
                    <Text size="sm" c="dimmed">Сумма весов:</Text>
                    <Text size="md" fw={700} c={sumOk ? 'green' : 'ktzGold'} ff="var(--font-mono), monospace">
                        {totalWeight.toFixed(3)}
                    </Text>
                    {!sumOk && <Text size="xs" c="ktzGold">Рекомендуется 1.000</Text>}
                </Group>
            </Card>

            <Table striped highlightOnHover verticalSpacing="xs">
                <Table.Thead>
                    <Table.Tr>
                        <Table.Th>Датчик</Table.Th>
                        <Table.Th>Вес</Table.Th>
                        <Table.Th w={180}>Визуализация</Table.Th>
                        <Table.Th />
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {weights.map((w) => {
                        const val = getValue(w.sensor_type, w.weight);
                        const modified = w.sensor_type in edits;
                        return (
                            <Table.Tr key={w.sensor_type} style={modified ? { backgroundColor: 'rgba(254,198,4,0.04)' } : undefined}>
                                <Table.Td>
                                    <Text size="sm" fw={500}>{SENSOR_LABELS[w.sensor_type] ?? w.sensor_type}</Text>
                                    <Text size="xs" c="dimmed" ff="var(--font-mono), monospace">{w.sensor_type}</Text>
                                </Table.Td>
                                <Table.Td>
                                    <NumberInput value={val} onChange={(v) => setEdits((p) => ({ ...p, [w.sensor_type]: Number(v) }))} min={0} max={1} step={0.01} decimalScale={3} size="xs" w={90} styles={modified ? { input: { borderColor: 'var(--mantine-color-ktzGold-5)' } } : {}} />
                                </Table.Td>
                                <Table.Td>
                                    <Progress value={val * 100} color={val > 0.15 ? 'critical' : val > 0.08 ? 'ktzGold' : 'ktzBlue'} size="md" radius="xl" />
                                </Table.Td>
                                <Table.Td>
                                    <Button size="xs" variant={modified ? 'filled' : 'subtle'} color={modified ? 'ktzGold' : 'gray'} leftSection={<IconDeviceFloppy size={14} />} onClick={() => handleSave(w.sensor_type, w.weight)} loading={saving[w.sensor_type]} disabled={!modified}>
                                        Сохранить
                                    </Button>
                                </Table.Td>
                            </Table.Tr>
                        );
                    })}
                    {weights.length === 0 && !isLoading && (
                        <Table.Tr><Table.Td colSpan={4}><Text ta="center" c="dimmed" size="sm">Нет данных</Text></Table.Td></Table.Tr>
                    )}
                </Table.Tbody>
            </Table>
        </Stack>
    );
}

function UsersTab() {
    const { data, isLoading } = useGetUsersQuery();
    const users = data?.users ?? [];
    const total = data?.total ?? 0;

    return (
        <Stack gap="md">
            <Group gap="md">
                <Card padding="xs" withBorder style={{ flex: 1 }}>
                    <Group gap="sm">
                        <ThemeIcon variant="light" color="ktzBlue" size="md">
                            <IconUsers size={16} />
                        </ThemeIcon>
                        <div>
                            <Text size="xs" c="dimmed">Всего</Text>
                            <Text size="lg" fw={700} ff="var(--font-mono), monospace">{total}</Text>
                        </div>
                    </Group>
                </Card>
                <Card padding="xs" withBorder style={{ flex: 1 }}>
                    <Group gap="sm">
                        <ThemeIcon variant="light" color="ktzGold" size="md">
                            <IconShieldCheck size={16} />
                        </ThemeIcon>
                        <div>
                            <Text size="xs" c="dimmed">Администраторы</Text>
                            <Text size="lg" fw={700} ff="var(--font-mono), monospace">
                                {users.filter((u) => u.role === 'admin').length}
                            </Text>
                        </div>
                    </Group>
                </Card>
                <Card padding="xs" withBorder style={{ flex: 1 }}>
                    <Group gap="sm">
                        <ThemeIcon variant="light" color="healthy" size="md">
                            <IconUser size={16} />
                        </ThemeIcon>
                        <div>
                            <Text size="xs" c="dimmed">Операторы</Text>
                            <Text size="lg" fw={700} ff="var(--font-mono), monospace">
                                {users.filter((u) => u.role === 'operator').length}
                            </Text>
                        </div>
                    </Group>
                </Card>
            </Group>

            {isLoading ? (
                <Center py="xl"><Text c="dimmed">Загрузка...</Text></Center>
            ) : users.length === 0 ? (
                <Center py="xl"><Text c="dimmed">Нет пользователей</Text></Center>
            ) : (
                <Table striped highlightOnHover verticalSpacing="sm">
                    <Table.Thead>
                        <Table.Tr>
                            <Table.Th>Пользователь</Table.Th>
                            <Table.Th>Роль</Table.Th>
                            <Table.Th>Дата регистрации</Table.Th>
                            <Table.Th>ID</Table.Th>
                        </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                        {users.map((user) => (
                            <Table.Tr key={user.id}>
                                <Table.Td>
                                    <Group gap="sm">
                                        <ThemeIcon variant="light" color={user.role === 'admin' ? 'ktzGold' : 'ktzBlue'} size="sm" radius="xl">
                                            {user.role === 'admin' ? <IconShieldCheck size={12} /> : <IconUser size={12} />}
                                        </ThemeIcon>
                                        <Text size="sm" fw={500}>{user.username}</Text>
                                    </Group>
                                </Table.Td>
                                <Table.Td>
                                    <Badge
                                        variant="light"
                                        color={user.role === 'admin' ? 'ktzGold' : 'ktzBlue'}
                                        size="sm"
                                    >
                                        {user.role === 'admin' ? 'Администратор' : 'Оператор'}
                                    </Badge>
                                </Table.Td>
                                <Table.Td>
                                    <Text size="sm" c="dimmed">
                                        {user.created_at ? formatDateTime(user.created_at) : '—'}
                                    </Text>
                                </Table.Td>
                                <Table.Td>
                                    <Text size="xs" c="dimmed" ff="var(--font-mono), monospace">
                                        {user.id.slice(0, 8)}...
                                    </Text>
                                </Table.Td>
                            </Table.Tr>
                        ))}
                    </Table.Tbody>
                </Table>
            )}
        </Stack>
    );
}

export function ConfigPage() {
    const isAdmin = useAppSelector(selectIsAdmin);

    if (!isAdmin) {
        return (
            <Center h="50vh">
                <Stack align="center" gap="md">
                    <ThemeIcon size={64} radius="xl" variant="light" color="red">
                        <IconAlertCircle size={32} />
                    </ThemeIcon>
                    <Text size="lg" fw={600}>Доступ запрещён</Text>
                    <Text size="sm" c="dimmed" ta="center" maw={300}>
                        Только администраторы могут просматривать и изменять настройки системы
                    </Text>
                </Stack>
            </Center>
        );
    }

    return (
        <Stack gap="lg">
            <Group justify="space-between">
                <Group gap="sm">
                    <ThemeIcon variant="light" color="ktzBlue" size="lg">
                        <IconAdjustments size={20} />
                    </ThemeIcon>
                    <Title order={3}>Настройки системы</Title>
                </Group>
                <Badge color="ktzGold" variant="light" size="lg" leftSection={<IconShieldCheck size={12} />}>
                    Администратор
                </Badge>
            </Group>

            <Card padding="lg" withBorder>
                <Tabs defaultValue="thresholds">
                    <Tabs.List>
                        <Tabs.Tab value="thresholds" leftSection={<IconGauge size={16} />}>
                            Пороги
                        </Tabs.Tab>
                        <Tabs.Tab value="weights" leftSection={<IconAdjustments size={16} />}>
                            Веса
                        </Tabs.Tab>
                        <Tabs.Tab value="users" leftSection={<IconUsers size={16} />}>
                            Пользователи
                        </Tabs.Tab>
                    </Tabs.List>

                    <Tabs.Panel value="thresholds" pt="md">
                        <Text size="sm" c="dimmed" mb="md">
                            Допустимые диапазоны значений для каждого датчика. Выход за пределы влияет на индекс здоровья.
                        </Text>
                        <ThresholdsTab />
                    </Tabs.Panel>

                    <Tabs.Panel value="weights" pt="md">
                        <Text size="sm" c="dimmed" mb="md">
                            Весовые коэффициенты вклада каждого датчика в общий индекс здоровья.
                        </Text>
                        <WeightsTab />
                    </Tabs.Panel>

                    <Tabs.Panel value="users" pt="md">
                        <Text size="sm" c="dimmed" mb="md">
                            Зарегистрированные пользователи системы мониторинга.
                        </Text>
                        <UsersTab />
                    </Tabs.Panel>
                </Tabs>
            </Card>
        </Stack>
    );
}
