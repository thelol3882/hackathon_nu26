'use client';

import {Card, Loader, Progress, Text, Group, Badge, Stack, ThemeIcon} from '@mantine/core';
import {IconHeartbeat} from '@tabler/icons-react';
import type {HealthIndex} from '@/features/health/types';
import classes from './HealthIndexGauge.module.css';

interface HealthIndexGaugeProps {
    health: HealthIndex | null;
    isLoading: boolean;
}

const SENSOR_LABELS: Record<string, string> = {
    diesel_rpm: 'Об. двигателя',
    oil_pressure: 'Давл. масла',
    coolant_temp: 'Охл. жидкость',
    fuel_level: 'Ур. топлива',
    fuel_rate: 'Расх. топлива',
    traction_motor_temp: 'Темп. тяг. двиг.',
    crankcase_pressure: 'Давл. картера',
    speed_actual: 'Скорость',
    speed_target: 'Скор. уставка',
    brake_pipe_pressure: 'Торм. магистраль',
    wheel_slip_ratio: 'Буксование',
    catenary_voltage: 'Напр. контакт. сети',
    pantograph_current: 'Ток пантографа',
    transformer_temp: 'Темп. трансф.',
    igbt_temp: 'Темп. IGBT',
    dc_link_voltage: 'Напр. DC-звена',
    recuperation_current: 'Ток рекуперации',
};

const CIRCUMFERENCE = 2 * Math.PI * 85;

function getColorVar(score: number): string {
    if (score >= 80) return 'var(--mantine-color-healthy-5)';
    if (score >= 50) return 'var(--mantine-color-ktzGold-5)';
    return 'var(--mantine-color-critical-5)';
}

function getGlowClass(category: string): string {
    switch (category) {
        case 'Норма':
            return 'panel-glow-healthy';
        case 'Внимание':
            return 'panel-glow-warning';
        case 'Критично':
            return 'panel-glow-critical';
        default:
            return '';
    }
}

function getProgressColor(score: number): string {
    if (score >= 80) return 'healthy';
    if (score >= 50) return 'ktzGold';
    return 'critical';
}

function getCategoryColor(category: string): string {
    switch (category) {
        case 'Норма':
            return 'green';
        case 'Внимание':
            return 'yellow';
        case 'Критично':
            return 'red';
        default:
            return 'gray';
    }
}

export function HealthIndexGauge({health, isLoading}: HealthIndexGaugeProps) {
    if (isLoading) {
        return (
            <Card>
                <div className={classes.loaderWrap}>
                    <Stack align="center" gap="sm">
                        <Loader size="lg" color="ktzBlue"/>
                        <Text size="xs" c="dimmed">
                            Загрузка индекса...
                        </Text>
                    </Stack>
                </div>
            </Card>
        );
    }

    if (!health) {
        return (
            <Card>
                <div className={classes.emptyState}>
                    <Stack align="center" gap="sm">
                        <ThemeIcon size={48} variant="light" color="gray" radius="xl">
                            <IconHeartbeat size={24} stroke={1.2}/>
                        </ThemeIcon>
                        <Text c="dimmed" size="sm">
                            Ожидание данных...
                        </Text>
                    </Stack>
                </div>
            </Card>
        );
    }

    const score = health.overall_score;
    const colorVar = getColorVar(score);
    const glowClass = getGlowClass(health.category);
    const dashOffset = CIRCUMFERENCE * (1 - score / 100);
    const factors = (health.top_factors ?? []).slice(0, 5);

    return (
        <Card className={glowClass}>
            <Group gap={4} mb="xs">
                <Text className="panel-label">ИНДЕКС ЗДОРОВЬЯ</Text>
                <Badge size="sm" variant="filled" color={getCategoryColor(health.category)}>
                    {health.category}
                </Badge>
            </Group>

            <div className={classes.wrapper}>
                <div className={classes.gaugeContainer}>
                    <svg viewBox="0 0 200 200" width="100%" height="100%">
                        <defs>
                            <filter id="gaugeGlow" x="-20%" y="-20%" width="140%" height="140%">
                                <feGaussianBlur stdDeviation="4" result="blur"/>
                                <feMerge>
                                    <feMergeNode in="blur"/>
                                    <feMergeNode in="SourceGraphic"/>
                                </feMerge>
                            </filter>
                        </defs>

                        <circle
                            cx={100}
                            cy={100}
                            r={85}
                            fill="none"
                            stroke="var(--dashboard-border)"
                            strokeWidth={10}
                            opacity={0.4}
                        />

                        <circle
                            className={classes.ring}
                            cx={100}
                            cy={100}
                            r={85}
                            fill="none"
                            stroke={colorVar}
                            strokeWidth={10}
                            strokeLinecap="round"
                            strokeDasharray={CIRCUMFERENCE}
                            strokeDashoffset={dashOffset}
                            transform="rotate(-90 100 100)"
                            filter="url(#gaugeGlow)"
                        />

                        <text
                            className={classes.score}
                            x={100}
                            y={92}
                            textAnchor="middle"
                            dominantBaseline="central"
                            fill={colorVar}
                            fontFamily="var(--font-mono), monospace"
                            fontSize={52}
                            fontWeight="bold"
                        >
                            {Math.round(score)}
                        </text>

                        <text
                            x={100}
                            y={122}
                            textAnchor="middle"
                            dominantBaseline="central"
                            fill="var(--dashboard-text-secondary)"
                            fontSize={11}
                        >
                            из 100
                        </text>
                    </svg>
                </div>

                {factors.length > 0 && (
                    <div className={classes.factorsContainer}>
                        <Group gap={4} mb={8} justify="center">
                            <Text size="xs" c="dimmed" fw={500}>
                                Влияющие факторы
                            </Text>
                        </Group>
                        {factors.map((factor) => (
                            <div key={factor.sensor_type} className={classes.factorRow}>
                                <span className={classes.factorLabel}>
                                    {SENSOR_LABELS[factor.sensor_type] ?? factor.sensor_type}
                                </span>
                                <Progress
                                    className={classes.factorBar}
                                    value={Math.min(100, Math.abs(factor.contribution_pct))}
                                    color={getProgressColor(score)}
                                    size="sm"
                                    radius="xl"
                                />
                                <span
                                    className={classes.factorValue}
                                    style={{
                                        color:
                                            factor.deviation_pct > 20
                                                ? 'var(--mantine-color-critical-5)'
                                                : factor.deviation_pct > 10
                                                    ? 'var(--mantine-color-ktzGold-5)'
                                                    : undefined,
                                    }}
                                >
                                    {factor.deviation_pct > 0 ? '+' : ''}
                                    {factor.deviation_pct.toFixed(1)}%
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </Card>
    );
}
