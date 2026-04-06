'use client';

/**
 * Per-locomotive simulation control panel.
 *
 * Shows the operator's current settings (route, sub-segment, scenario,
 * mode) and lets them edit any of them inline. The big red
 * "Аварийный сценарий" button is the headline action — one click and
 * the locomotive trips its brake-pipe scenario, which the state
 * machine in `services/simulator/.../locomotive_state.py` immediately
 * snaps into EMERGENCY mode and forces to a stop.
 *
 * Edits are debounced into a single PATCH on `Сохранить`. We don't
 * try to live-sync per-keystroke — operator actions are deliberate.
 */

import { useMemo, useState } from 'react';
import {
    Alert,
    Badge,
    Box,
    Button,
    Card,
    Center,
    Group,
    Loader,
    NumberInput,
    Select,
    Stack,
    Switch,
    Text,
} from '@mantine/core';
import { IconBolt, IconPencil, IconRefresh } from '@tabler/icons-react';
import { useGetRoutesQuery } from '@/features/routes';
import {
    useGetSimulatedLocomotiveQuery,
    useUpdateSimulatedLocomotiveMutation,
    type LocomotiveScenario,
    type OnArrival,
} from '@/features/simulator';

interface Props {
    locomotiveId: string;
}

const SCENARIOS: { value: LocomotiveScenario; label: string }[] = [
    { value: 'normal', label: 'Норма' },
    { value: 'degradation', label: 'Деградация' },
    { value: 'emergency', label: 'Авария' },
];

const ON_ARRIVAL: { value: OnArrival; label: string }[] = [
    { value: 'loop', label: 'По кольцу' },
    { value: 'stop', label: 'Остановиться в конечной' },
    { value: 'remove', label: 'Снять по прибытию' },
];

const SCENARIO_COLOR: Record<LocomotiveScenario, string> = {
    normal: 'teal',
    degradation: 'yellow',
    emergency: 'red',
};

export function SimulationControlPanel({ locomotiveId }: Props) {
    // Polling — operator changes propagate to the runner instantly,
    // but the inverse (kinematics moving the loco along the route)
    // also benefits from a slow refresh so the visible distance / km
    // stays accurate without leaning on a separate WS for runtime
    // metadata.
    const {
        data: live,
        isLoading,
        isFetching,
        refetch,
    } = useGetSimulatedLocomotiveQuery(locomotiveId, { pollingInterval: 5000 });
    const { data: routes = [] } = useGetRoutesQuery();
    const [patch, { isLoading: saving }] = useUpdateSimulatedLocomotiveMutation();

    // Local edit state — initialised from `live` only at the moment
    // the operator clicks "Изменить" (see `enterEditMode` below). We
    // deliberately don't sync on every poll: if the user is mid-typing,
    // an incoming refresh would clobber their input. The Save button
    // PATCHes everything in one go and the form re-renders from the
    // fresh server state via the polling query.
    const [routeName, setRouteName] = useState<string | null>(null);
    const [startStation, setStartStation] = useState<string | null>(null);
    const [endStation, setEndStation] = useState<string | null>(null);
    const [scenario, setScenario] = useState<LocomotiveScenario>('normal');
    const [autoMode, setAutoMode] = useState(false);
    const [onArrival, setOnArrival] = useState<OnArrival>('loop');
    const [speed, setSpeed] = useState<number>(0);
    const [editing, setEditing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    /** Snapshot the current live state into the form's local state.
     *  Called when the operator clicks "Изменить", not on each poll. */
    const enterEditMode = () => {
        if (!live) return;
        setRouteName(live.route_name);
        setScenario(live.scenario);
        setAutoMode(live.auto_mode);
        setOnArrival(live.on_arrival);
        setSpeed(Math.round(live.speed_kmh));
        // Resolve station names by km mark — the backend doesn't
        // echo names back, but km marks are unique within a route.
        const r = routes.find((x) => x.name === live.route_name);
        const matchByKm = (km: number) =>
            r?.stations.find((s) => Math.round(s.km_from_start) === Math.round(km))?.name ?? null;
        setStartStation(matchByKm(live.start_km));
        setEndStation(matchByKm(live.end_km));
        setEditing(true);
    };

    const stations = useMemo(() => {
        const r = routes.find((rt) => rt.name === routeName);
        return r?.stations ?? [];
    }, [routes, routeName]);
    const stationOptions = stations.map((s) => ({
        value: s.name,
        label: `${s.name} (${Math.round(s.km_from_start)} км)`,
    }));

    const handleSave = async () => {
        setError(null);
        try {
            await patch({
                id: locomotiveId,
                body: {
                    route_name: routeName ?? undefined,
                    start_station: startStation,
                    end_station: endStation,
                    scenario,
                    auto_mode: autoMode,
                    on_arrival: onArrival,
                    speed_kmh: speed,
                },
            }).unwrap();
            setEditing(false);
        } catch (e) {
            const detail =
                (e as { data?: { detail?: string } })?.data?.detail ??
                (e as Error)?.message ??
                'Ошибка';
            setError(String(detail));
        }
    };

    const handleEmergency = async () => {
        setError(null);
        try {
            await patch({
                id: locomotiveId,
                body: { scenario: 'emergency' },
            }).unwrap();
        } catch (e) {
            setError((e as Error).message);
        }
    };

    const handleResetScenario = async () => {
        setError(null);
        try {
            await patch({
                id: locomotiveId,
                body: { scenario: 'normal' },
            }).unwrap();
        } catch (e) {
            setError((e as Error).message);
        }
    };

    if (isLoading || !live) {
        return (
            <Card style={{ borderTop: '2px solid var(--mantine-color-ktzGold-5)' }}>
                <Center h={120}>
                    <Loader size="sm" />
                </Center>
            </Card>
        );
    }

    return (
        <Card style={{ borderTop: '2px solid var(--mantine-color-ktzGold-5)' }}>
            <Group justify="space-between" mb="sm" wrap="wrap">
                <Group gap="sm">
                    <Text className="panel-label">СИМУЛЯЦИЯ</Text>
                    <Badge size="xs" variant="light" color={SCENARIO_COLOR[live.scenario]}>
                        {live.scenario}
                    </Badge>
                    <Badge size="xs" variant="default">
                        {live.mode}
                    </Badge>
                    {isFetching && <Loader size={12} />}
                </Group>
                <Group gap="xs">
                    {!editing ? (
                        <Button
                            size="xs"
                            variant="light"
                            leftSection={<IconPencil size={12} />}
                            onClick={enterEditMode}
                        >
                            Изменить
                        </Button>
                    ) : (
                        <>
                            <Button
                                size="xs"
                                variant="default"
                                onClick={() => {
                                    setEditing(false);
                                    refetch();
                                }}
                                disabled={saving}
                            >
                                Отмена
                            </Button>
                            <Button size="xs" loading={saving} onClick={handleSave}>
                                Сохранить
                            </Button>
                        </>
                    )}
                </Group>
            </Group>

            <Stack gap="xs">
                {!editing ? (
                    <Group gap="md" wrap="wrap">
                        <Box>
                            <Text size="xs" c="dimmed">
                                Маршрут
                            </Text>
                            <Text size="sm" fw={500}>
                                {live.route_name}
                            </Text>
                        </Box>
                        <Box>
                            <Text size="xs" c="dimmed">
                                Сегмент
                            </Text>
                            <Text size="sm">
                                {live.start_km.toFixed(0)} → {live.end_km.toFixed(0)} км
                            </Text>
                        </Box>
                        <Box>
                            <Text size="xs" c="dimmed">
                                Прогресс
                            </Text>
                            <Text size="sm">
                                {(live.segment_progress * 100).toFixed(1)}% (
                                {live.distance_km.toFixed(1)} км)
                            </Text>
                        </Box>
                        <Box>
                            <Text size="xs" c="dimmed">
                                Скорость
                            </Text>
                            <Text size="sm">{live.speed_kmh.toFixed(0)} км/ч</Text>
                        </Box>
                        <Box>
                            <Text size="xs" c="dimmed">
                                Курс
                            </Text>
                            <Text size="sm">{live.bearing_deg.toFixed(0)}°</Text>
                        </Box>
                        <Box>
                            <Text size="xs" c="dimmed">
                                По прибытию
                            </Text>
                            <Text size="sm">{live.on_arrival}</Text>
                        </Box>
                        <Box>
                            <Text size="xs" c="dimmed">
                                Авто
                            </Text>
                            <Text size="sm">{live.auto_mode ? 'да' : 'нет'}</Text>
                        </Box>
                    </Group>
                ) : (
                    <Stack gap="xs">
                        <Group grow>
                            <Select
                                size="xs"
                                label="Маршрут"
                                data={routes.map((r) => ({
                                    value: r.name,
                                    label: r.name,
                                }))}
                                value={routeName}
                                onChange={(v) => {
                                    setRouteName(v);
                                    setStartStation(null);
                                    setEndStation(null);
                                }}
                                searchable
                            />
                            <Select
                                size="xs"
                                label="Состояние"
                                data={SCENARIOS}
                                value={scenario}
                                onChange={(v) => v && setScenario(v as LocomotiveScenario)}
                                allowDeselect={false}
                            />
                        </Group>
                        <Group grow>
                            <Select
                                size="xs"
                                label="Откуда"
                                data={stationOptions}
                                value={startStation}
                                onChange={setStartStation}
                                clearable
                                searchable
                                disabled={!routeName}
                            />
                            <Select
                                size="xs"
                                label="Куда"
                                data={stationOptions}
                                value={endStation}
                                onChange={setEndStation}
                                clearable
                                searchable
                                disabled={!routeName}
                            />
                        </Group>
                        <Group grow>
                            <Select
                                size="xs"
                                label="По прибытию"
                                data={ON_ARRIVAL}
                                value={onArrival}
                                onChange={(v) => v && setOnArrival(v as OnArrival)}
                                allowDeselect={false}
                            />
                            <NumberInput
                                size="xs"
                                label="Скорость, км/ч"
                                value={speed}
                                onChange={(v) => setSpeed(typeof v === 'number' ? v : 0)}
                                min={0}
                                max={140}
                                step={5}
                            />
                        </Group>
                        <Switch
                            size="sm"
                            label="Авто-режим (state machine ведёт сама)"
                            checked={autoMode}
                            onChange={(e) => setAutoMode(e.currentTarget.checked)}
                        />
                    </Stack>
                )}

                <Group gap="xs" justify="space-between" wrap="wrap" mt="xs">
                    <Group gap="xs">
                        <Button
                            size="xs"
                            color="red"
                            leftSection={<IconBolt size={14} />}
                            onClick={handleEmergency}
                            disabled={live.scenario === 'emergency'}
                            loading={saving}
                        >
                            Аварийный сценарий
                        </Button>
                        <Button
                            size="xs"
                            variant="light"
                            color="teal"
                            leftSection={<IconRefresh size={14} />}
                            onClick={handleResetScenario}
                            disabled={live.scenario === 'normal'}
                            loading={saving}
                        >
                            Вернуть в норму
                        </Button>
                    </Group>
                </Group>

                {error && (
                    <Alert color="red" mt="xs">
                        {error}
                    </Alert>
                )}
            </Stack>
        </Card>
    );
}
