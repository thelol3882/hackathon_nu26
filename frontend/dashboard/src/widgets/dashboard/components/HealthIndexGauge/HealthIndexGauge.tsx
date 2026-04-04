'use client';

import { Card, Loader, Progress, Text } from '@mantine/core';
import type { HealthIndex } from '@/features/health/types';
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
    traction_motor_temp: 'Темп. тяг. двиг.',
    speed_actual: 'Скорость',
    brake_pipe_pressure: 'Торм. магистраль',
    catenary_voltage: 'Напр. контакт. сети',
    pantograph_current: 'Ток пантографа',
    transformer_temp: 'Темп. трансф.',
    igbt_temp: 'Темп. IGBT',
};

const CIRCUMFERENCE = 2 * Math.PI * 85;

const TICK_POSITIONS = [0, 0.25, 0.5, 0.75, 1];

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

function buildTickMarks() {
    const r = 85;
    const cx = 100;
    const cy = 100;
    const innerR = r - 8;
    const outerR = r + 8;

    return TICK_POSITIONS.map((pct) => {
        // Angle starts at top (-90deg) and goes clockwise
        const angle = -90 + pct * 360;
        const rad = (angle * Math.PI) / 180;
        const x1 = cx + innerR * Math.cos(rad);
        const y1 = cy + innerR * Math.sin(rad);
        const x2 = cx + outerR * Math.cos(rad);
        const y2 = cy + outerR * Math.sin(rad);
        return <line key={pct} className={classes.tickMark} x1={x1} y1={y1} x2={x2} y2={y2} />;
    });
}

export function HealthIndexGauge({ health, isLoading }: HealthIndexGaugeProps) {
    if (isLoading) {
        return (
            <Card className="">
                <div className={classes.loaderWrap}>
                    <Loader size="lg" />
                </div>
            </Card>
        );
    }

    if (!health) {
        return (
            <Card>
                <div className={classes.emptyState}>
                    <Text c="dimmed">Нет данных</Text>
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
            <div className={classes.wrapper}>
                <div className={classes.gaugeContainer}>
                    <svg viewBox="0 0 200 200" width="100%" height="100%">
                        {/* Background ring */}
                        <circle
                            cx={100}
                            cy={100}
                            r={85}
                            fill="none"
                            stroke="var(--dashboard-border)"
                            strokeWidth={12}
                        />

                        {/* Tick marks */}
                        {buildTickMarks()}

                        {/* Foreground ring */}
                        <circle
                            className={classes.ring}
                            cx={100}
                            cy={100}
                            r={85}
                            fill="none"
                            stroke={colorVar}
                            strokeWidth={12}
                            strokeLinecap="round"
                            strokeDasharray={CIRCUMFERENCE}
                            strokeDashoffset={dashOffset}
                            transform="rotate(-90 100 100)"
                        />

                        {/* Score number */}
                        <text
                            className={classes.score}
                            x={100}
                            y={100}
                            textAnchor="middle"
                            dominantBaseline="central"
                            fill={colorVar}
                            fontFamily="var(--font-mono), monospace"
                            fontSize={48}
                            fontWeight="bold"
                        >
                            {Math.round(score)}
                        </text>

                        {/* Category label */}
                        <text
                            className={classes.score}
                            x={100}
                            y={130}
                            textAnchor="middle"
                            dominantBaseline="central"
                            fill={colorVar}
                            fontSize={14}
                        >
                            {health.category}
                        </text>
                    </svg>
                </div>

                {factors.length > 0 && (
                    <div className={classes.factorsContainer}>
                        <Text size="xs" c="dimmed" mb={8} ta="center">
                            Влияющие факторы
                        </Text>
                        {factors.map((factor) => (
                            <div key={factor.sensor_type} className={classes.factorRow}>
                                <span className={classes.factorLabel}>
                                    {SENSOR_LABELS[factor.sensor_type] ?? factor.sensor_type}
                                </span>
                                <Progress
                                    className={classes.factorBar}
                                    value={factor.contribution_pct}
                                    color={getProgressColor(score)}
                                    size="sm"
                                    radius="xl"
                                />
                                <span className={classes.factorValue}>
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
