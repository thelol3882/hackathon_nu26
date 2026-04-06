'use client';

// Two-stage create: POST /locomotives (catalogue) then POST /simulator/locomotives
// with the same UUID. If stage 2 fails, the catalogue row is left in place and
// the user can retry from there.

import { useMemo, useState } from 'react';
import {
    Alert,
    Button,
    Group,
    Modal,
    NumberInput,
    Select,
    Stack,
    Switch,
    TextInput,
} from '@mantine/core';
import { useCreateLocomotiveMutation } from '@/features/locomotives';
import { useGetRoutesQuery } from '@/features/routes';
import {
    useCreateSimulatedLocomotiveMutation,
    type LocomotiveScenario,
    type LocomotiveType,
    type OnArrival,
} from '@/features/simulator';

interface Props {
    opened: boolean;
    onClose: () => void;
    onCreated?: (locoId: string) => void;
}

const TYPES: { value: LocomotiveType; label: string }[] = [
    { value: 'TE33A', label: 'ТЭ33А (тепловоз)' },
    { value: 'KZ8A', label: 'KZ8A (электровоз)' },
];

const SCENARIOS: { value: LocomotiveScenario; label: string }[] = [
    { value: 'normal', label: 'Норма — все параметры в порядке' },
    { value: 'degradation', label: 'Деградация — постепенный перегрев IGBT' },
    { value: 'emergency', label: 'Авария — обрыв тормозной магистрали' },
];

const ON_ARRIVAL: { value: OnArrival; label: string }[] = [
    { value: 'loop', label: 'По кольцу: туда-сюда' },
    { value: 'stop', label: 'Остановиться в конечной' },
    { value: 'remove', label: 'Снять с симуляции по прибытию' },
];

export function CreateLocomotiveModal({ opened, onClose, onCreated }: Props) {
    const { data: routes = [] } = useGetRoutesQuery();
    const [createCatalog, catalogState] = useCreateLocomotiveMutation();
    const [createSim, simState] = useCreateSimulatedLocomotiveMutation();

    const [name, setName] = useState('');
    const [type, setType] = useState<LocomotiveType>('TE33A');
    const [routeName, setRouteName] = useState<string | null>(null);
    const [startStation, setStartStation] = useState<string | null>(null);
    const [endStation, setEndStation] = useState<string | null>(null);
    const [scenario, setScenario] = useState<LocomotiveScenario>('normal');
    const [autoMode, setAutoMode] = useState(true);
    const [onArrival, setOnArrival] = useState<OnArrival>('loop');
    const [initialSpeed, setInitialSpeed] = useState<number>(60);
    const [error, setError] = useState<string | null>(null);

    // KZ8A is electric, so only electrified routes can host it.
    const electrifiedOnly = type === 'KZ8A';
    const filteredRoutes = useMemo(
        () => (electrifiedOnly ? routes.filter((r) => r.electrified) : routes),
        [routes, electrifiedOnly],
    );

    // Event handler (not effect) so the reset stays bound to a user action.
    const handleTypeChange = (next: LocomotiveType) => {
        setType(next);
        if (next === 'KZ8A' && routeName) {
            const stillOk = routes.some((r) => r.name === routeName && r.electrified);
            if (!stillOk) {
                setRouteName(null);
                setStartStation(null);
                setEndStation(null);
            }
        }
    };

    const stations = useMemo(() => {
        const r = routes.find((rt) => rt.name === routeName);
        return r?.stations ?? [];
    }, [routes, routeName]);

    const stationOptions = stations.map((s) => ({
        value: s.name,
        label: `${s.name} (${Math.round(s.km_from_start)} км)`,
    }));

    const reset = () => {
        setName('');
        setType('TE33A');
        setRouteName(null);
        setStartStation(null);
        setEndStation(null);
        setScenario('normal');
        setAutoMode(true);
        setOnArrival('loop');
        setInitialSpeed(60);
        setError(null);
    };

    const handleClose = () => {
        if (catalogState.isLoading || simState.isLoading) return;
        reset();
        onClose();
    };

    const handleSubmit = async () => {
        setError(null);
        if (!name.trim()) {
            setError('Введите название локомотива');
            return;
        }
        if (!routeName) {
            setError('Выберите маршрут');
            return;
        }
        try {
            // Stage 1: catalogue insert. Serial/manufacturer/year are auto-filled.
            const catalog = await createCatalog({
                serial_number: `SIM-${Date.now().toString(36).toUpperCase()}`,
                model: type,
                manufacturer: type === 'KZ8A' ? 'Alstom' : 'GE Transportation',
                year_manufactured: new Date().getFullYear(),
            }).unwrap();

            // Stage 2: simulator spawn with the same UUID.
            await createSim({
                id: catalog.id,
                loco_type: type,
                route_name: routeName,
                name: name.trim(),
                start_station: startStation,
                end_station: endStation,
                scenario,
                auto_mode: autoMode,
                on_arrival: onArrival,
                initial_speed_kmh: initialSpeed,
                mode: autoMode ? 'cruising' : 'depot',
            }).unwrap();

            onCreated?.(catalog.id);
            reset();
            onClose();
        } catch (e) {
            const detail =
                (e as { data?: { detail?: string } })?.data?.detail ??
                (e as Error)?.message ??
                'Неизвестная ошибка';
            setError(String(detail));
        }
    };

    const submitting = catalogState.isLoading || simState.isLoading;

    return (
        <Modal opened={opened} onClose={handleClose} title="Создать локомотив" centered size="lg">
            <Stack gap="md">
                <TextInput
                    label="Название"
                    placeholder="Например: Поезд 042А Алматы → Астана"
                    value={name}
                    onChange={(e) => setName(e.currentTarget.value)}
                    required
                />
                <Select
                    label="Модель"
                    data={TYPES}
                    value={type}
                    onChange={(v) => v && handleTypeChange(v as LocomotiveType)}
                    allowDeselect={false}
                />
                <Select
                    label="Маршрут"
                    placeholder={
                        electrifiedOnly ? 'Только электрифицированные' : 'Любой маршрут KTZ'
                    }
                    data={filteredRoutes.map((r) => ({
                        value: r.name,
                        label: `${r.name} · ${Math.round(r.length_km)} км${r.electrified ? ' ⚡' : ''}`,
                    }))}
                    value={routeName}
                    onChange={(v) => {
                        setRouteName(v);
                        setStartStation(null);
                        setEndStation(null);
                    }}
                    searchable
                    required
                />
                <Group grow>
                    <Select
                        label="Откуда"
                        placeholder={routeName ? 'Начало маршрута' : '...'}
                        data={stationOptions}
                        value={startStation}
                        onChange={setStartStation}
                        disabled={!routeName}
                        clearable
                        searchable
                    />
                    <Select
                        label="Куда"
                        placeholder={routeName ? 'Конец маршрута' : '...'}
                        data={stationOptions}
                        value={endStation}
                        onChange={setEndStation}
                        disabled={!routeName}
                        clearable
                        searchable
                    />
                </Group>
                <Select
                    label="Состояние"
                    data={SCENARIOS}
                    value={scenario}
                    onChange={(v) => v && setScenario(v as LocomotiveScenario)}
                    allowDeselect={false}
                />
                <Group grow>
                    <Select
                        label="По прибытию"
                        data={ON_ARRIVAL}
                        value={onArrival}
                        onChange={(v) => v && setOnArrival(v as OnArrival)}
                        allowDeselect={false}
                    />
                    <NumberInput
                        label="Начальная скорость, км/ч"
                        description="Реалистично 40–110. Auto-режим зажмёт > 110 — отключи его для безумных скоростей"
                        value={initialSpeed}
                        onChange={(v) => setInitialSpeed(typeof v === 'number' ? v : 0)}
                        min={0}
                        max={500}
                        step={5}
                    />
                </Group>
                <Switch
                    label="Сразу запустить (иначе остаётся в депо)"
                    checked={autoMode}
                    onChange={(e) => setAutoMode(e.currentTarget.checked)}
                />

                {error && (
                    <Alert color="red" title="Не удалось создать">
                        {error}
                    </Alert>
                )}

                <Group justify="flex-end" gap="sm">
                    <Button variant="default" onClick={handleClose} disabled={submitting}>
                        Отмена
                    </Button>
                    <Button onClick={handleSubmit} loading={submitting}>
                        Создать
                    </Button>
                </Group>
            </Stack>
        </Modal>
    );
}
