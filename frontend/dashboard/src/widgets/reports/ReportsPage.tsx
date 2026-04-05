'use client';

import {useCallback, useState} from 'react';
import {
    ActionIcon,
    Alert,
    Badge,
    Button,
    Card,
    Center,
    Grid,
    Group,
    Loader,
    Progress,
    SimpleGrid,
    Stack,
    Stepper,
    Text,
    ThemeIcon,
    Title,
    Tooltip,
    UnstyledButton,
} from '@mantine/core';
import {DateInput} from '@mantine/dates';
import {
    IconAlertCircle,
    IconCheck,
    IconClock,
    IconDownload,
    IconFileSpreadsheet,
    IconFileText,
    IconFileTypePdf,
    IconLoader,
    IconRefresh,
    IconTrain,
} from '@tabler/icons-react';
import {useGetReportsQuery, useReportGeneration} from '@/features/reports';
import {LocomotiveSelect} from '@/features/locomotives';
import {formatDateTime, dayjs} from '@/shared/utils/date';
import {useAppSelector} from '@/store/hooks';
import {selectAccessToken} from '@/store/authSlice';
import type {ReportFormat, ReportStatus} from '@/features/reports/types';

const STATUS_COLOR: Record<ReportStatus, string> = {
    pending: 'blue',
    processing: 'yellow',
    completed: 'green',
    failed: 'red',
};

const STATUS_LABEL: Record<ReportStatus, string> = {
    pending: 'Ожидание',
    processing: 'Обработка',
    completed: 'Готов',
    failed: 'Ошибка',
};

const STATUS_ICON: Record<ReportStatus, typeof IconClock> = {
    pending: IconClock,
    processing: IconLoader,
    completed: IconCheck,
    failed: IconAlertCircle,
};

const FORMAT_META: Record<
    ReportFormat,
    { icon: typeof IconFileText; color: string; label: string; desc: string }
> = {
    pdf: {
        icon: IconFileTypePdf,
        color: 'critical',
        label: 'PDF',
        desc: 'Красивый отчёт с таблицами, графиками и цветами',
    },
    csv: {
        icon: IconFileSpreadsheet,
        color: 'healthy',
        label: 'CSV',
        desc: 'Табличные данные для Excel / Google Sheets',
    },
    json: {
        icon: IconFileText,
        color: 'ktzBlue',
        label: 'JSON',
        desc: 'Машиночитаемый формат для интеграций',
    },
};

function FormatCard({
                        fmt,
                        selected,
                        onClick,
                    }: {
    fmt: ReportFormat;
    selected: boolean;
    onClick: () => void;
}) {
    const meta = FORMAT_META[fmt];
    const FmtIcon = meta.icon;
    return (
        <UnstyledButton onClick={onClick} style={{width: '100%', height: '100%'}}>
            <Card
                padding="md"
                withBorder
                h="100%"
                style={{
                    cursor: 'pointer',
                    borderColor: selected ? `var(--mantine-color-${meta.color}-5)` : undefined,
                    borderWidth: selected ? 2 : 1,
                    backgroundColor: selected ? `var(--dashboard-surface-elevated)` : undefined,
                    transition: 'all 0.15s ease',
                }}
            >
                <Stack gap="xs" align="center" ta="center">
                    <ThemeIcon
                        variant={selected ? 'filled' : 'light'}
                        color={meta.color}
                        size="xl"
                        radius="md"
                    >
                        <FmtIcon size={24}/>
                    </ThemeIcon>
                    <Text size="sm" fw={600}>
                        {meta.label}
                    </Text>
                    <Text size="xs" c="dimmed" lineClamp={2}>
                        {meta.desc}
                    </Text>
                </Stack>
            </Card>
        </UnstyledButton>
    );
}

export function ReportsPage() {
    const token = useAppSelector(selectAccessToken);
    const [locomotiveId, setLocomotiveId] = useState<string | null>(null);
    const [format, setFormat] = useState<ReportFormat>('pdf');
    const [startDate, setStartDate] = useState<string | null>(null);
    const [endDate, setEndDate] = useState<string | null>(null);

    const {data: reports = []} = useGetReportsQuery({});
    const {generate, status, isGenerating, downloadUrl, reset} = useReportGeneration();

    const handleDownload = useCallback(
        async (url: string) => {
            const res = await fetch(url, {
                headers: token ? {Authorization: `Bearer ${token}`} : {},
            });
            if (!res.ok) return;
            const blob = await res.blob();
            const disposition = res.headers.get('Content-Disposition');
            const filename = disposition?.match(/filename="?(.+?)"?$/)?.[1] ?? 'report';
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            a.click();
            URL.revokeObjectURL(a.href);
        },
        [token],
    );

    const handleGenerate = () => {
        if (!startDate || !endDate) return;
        generate({
            locomotive_id: locomotiveId || null,
            report_type: 'telemetry',
            format,
            date_range: {
                start: dayjs(startDate).toISOString(),
                end: dayjs(endDate).toISOString(),
            },
        });
    };

    const FormatIcon = FORMAT_META[format].icon;

    const activeStep =
        status === 'completed' || status === 'failed'
            ? 3
            : isGenerating
                ? 2
                : startDate && endDate
                    ? 1
                    : 0;

    const completedReports = reports.filter((r) => r.status === 'completed');
    const failedReports = reports.filter((r) => r.status === 'failed');

    return (
        <Stack gap="lg">
            <Group justify="space-between">
                <Group gap="sm">
                    <ThemeIcon variant="light" color="ktzBlue" size="lg">
                        <IconFileText size={20}/>
                    </ThemeIcon>
                    <Title order={3}>Отчёты</Title>
                </Group>
                {reports.length > 0 && (
                    <Group gap="xs">
                        <Badge variant="light" color="green" size="sm">
                            {completedReports.length} готовых
                        </Badge>
                        {failedReports.length > 0 && (
                            <Badge variant="light" color="red" size="sm">
                                {failedReports.length} ошибок
                            </Badge>
                        )}
                    </Group>
                )}
            </Group>

            <Grid>
                <Grid.Col span={{base: 12, lg: 7}}>
                    <Card padding="lg" withBorder>
                        <Text fw={600} size="lg" mb="lg">
                            Генерация отчёта
                        </Text>

                        <Stepper active={activeStep} size="xs" mb="lg" color="ktzBlue">
                            <Stepper.Step label="Параметры" description="Локомотив и даты"/>
                            <Stepper.Step label="Формат" description="PDF, CSV или JSON"/>
                            <Stepper.Step label="Генерация" description="Обработка данных"/>
                            <Stepper.Step label="Готово" description="Скачать отчёт"/>
                        </Stepper>

                        <Stack gap="md">
                            <Card
                                withBorder
                                padding="sm"
                                style={{backgroundColor: 'var(--dashboard-surface-elevated)'}}
                            >
                                <Text size="xs" fw={600} c="dimmed" mb="xs" tt="uppercase">
                                    1. Выбор данных
                                </Text>
                                <Stack gap="sm">
                                    <LocomotiveSelect
                                        label="Локомотив"
                                        value={locomotiveId}
                                        onChange={setLocomotiveId}
                                        allowAll
                                        w="100%"
                                    />
                                    {!locomotiveId && (
                                        <Alert
                                            color="ktzGold"
                                            variant="light"
                                            icon={<IconTrain size={14}/>}
                                            py="xs"
                                        >
                                            <Text size="xs">
                                                Сводный отчёт по всему парку (агрегированные данные)
                                            </Text>
                                        </Alert>
                                    )}
                                    <SimpleGrid cols={2}>
                                        <DateInput
                                            label="Начало периода"
                                            placeholder="Выберите дату"
                                            value={startDate}
                                            onChange={setStartDate}
                                        />
                                        <DateInput
                                            label="Конец периода"
                                            placeholder="Выберите дату"
                                            value={endDate}
                                            onChange={setEndDate}
                                        />
                                    </SimpleGrid>
                                </Stack>
                            </Card>

                            <Card
                                withBorder
                                padding="sm"
                                style={{backgroundColor: 'var(--dashboard-surface-elevated)'}}
                            >
                                <Text size="xs" fw={600} c="dimmed" mb="xs" tt="uppercase">
                                    2. Формат отчёта
                                </Text>
                                <SimpleGrid cols={{base: 1, sm: 3}}>
                                    <FormatCard
                                        fmt="pdf"
                                        selected={format === 'pdf'}
                                        onClick={() => setFormat('pdf')}
                                    />
                                    <FormatCard
                                        fmt="csv"
                                        selected={format === 'csv'}
                                        onClick={() => setFormat('csv')}
                                    />
                                    <FormatCard
                                        fmt="json"
                                        selected={format === 'json'}
                                        onClick={() => setFormat('json')}
                                    />
                                </SimpleGrid>
                            </Card>

                            <Group>
                                <Button
                                    onClick={handleGenerate}
                                    loading={isGenerating}
                                    disabled={!startDate || !endDate}
                                    size="md"
                                    leftSection={<FormatIcon size={18}/>}
                                >
                                    Сгенерировать {FORMAT_META[format].label}
                                </Button>
                                <Button
                                    variant="subtle"
                                    color="gray"
                                    onClick={() => {
                                        setLocomotiveId(null);
                                        setFormat('pdf');
                                        setStartDate(null);
                                        setEndDate(null);
                                        reset();
                                    }}
                                    leftSection={<IconRefresh size={16}/>}
                                >
                                    Сбросить
                                </Button>
                            </Group>

                            {isGenerating && (
                                <Card
                                    withBorder
                                    padding="md"
                                    style={{
                                        borderColor: 'var(--mantine-color-ktzBlue-5)',
                                        borderStyle: 'dashed',
                                    }}
                                >
                                    <Group gap="md">
                                        <Loader size="md" color="ktzBlue"/>
                                        <Stack gap={2} style={{flex: 1}}>
                                            <Text size="sm" fw={600}>
                                                Генерация отчёта...
                                            </Text>
                                            <Text size="xs" c="dimmed">
                                                Агрегация данных, расчёт метрик, форматирование
                                            </Text>
                                            <Progress
                                                value={100}
                                                size="xs"
                                                animated
                                                color="ktzBlue"
                                            />
                                        </Stack>
                                    </Group>
                                </Card>
                            )}

                            {status === 'completed' && downloadUrl && (
                                <Card
                                    withBorder
                                    padding="md"
                                    style={{
                                        borderColor: 'var(--mantine-color-healthy-5)',
                                    }}
                                >
                                    <Group justify="space-between">
                                        <Group gap="md">
                                            <ThemeIcon
                                                variant="filled"
                                                color="green"
                                                size="xl"
                                                radius="xl"
                                            >
                                                <IconCheck size={24}/>
                                            </ThemeIcon>
                                            <Stack gap={0}>
                                                <Text size="md" fw={700}>
                                                    Отчёт готов!
                                                </Text>
                                                <Text size="sm" c="dimmed">
                                                    Формат: {FORMAT_META[format].label}
                                                </Text>
                                            </Stack>
                                        </Group>
                                        <Button
                                            variant="filled"
                                            color="green"
                                            size="md"
                                            leftSection={<IconDownload size={18}/>}
                                            onClick={() => handleDownload(downloadUrl)}
                                        >
                                            Скачать
                                        </Button>
                                    </Group>
                                </Card>
                            )}

                            {status === 'failed' && (
                                <Alert
                                    color="red"
                                    variant="light"
                                    icon={<IconAlertCircle size={18}/>}
                                    title="Ошибка генерации"
                                >
                                    Не удалось сгенерировать отчёт. Попробуйте уменьшить диапазон
                                    дат или выбрать конкретный локомотив.
                                </Alert>
                            )}
                        </Stack>
                    </Card>
                </Grid.Col>

                <Grid.Col span={{base: 12, lg: 5}}>
                    <Card padding="lg" withBorder h="100%">
                        <Group gap="xs" mb="md">
                            <ThemeIcon variant="light" color="gray" size="md">
                                <IconClock size={16}/>
                            </ThemeIcon>
                            <Text fw={600}>История</Text>
                            <Badge size="sm" variant="light" color="gray">
                                {reports.length}
                            </Badge>
                        </Group>

                        {reports.length === 0 ? (
                            <Center py="xl" style={{flex: 1}}>
                                <Stack align="center" gap="xs">
                                    <ThemeIcon variant="light" color="gray" size={48} radius="xl">
                                        <IconFileText size={24}/>
                                    </ThemeIcon>
                                    <Text c="dimmed" size="sm">
                                        Нет отчётов
                                    </Text>
                                    <Text c="dimmed" size="xs">
                                        Создайте первый отчёт
                                    </Text>
                                </Stack>
                            </Center>
                        ) : (
                            <Stack gap="xs">
                                {reports.map((report) => {
                                    const StatusIcon = STATUS_ICON[report.status];
                                    const fmtMeta = FORMAT_META[report.format] ?? FORMAT_META.json;
                                    const FmtIcon = fmtMeta.icon;
                                    const isReady = report.status === 'completed';

                                    return (
                                        <Card
                                            key={report.report_id}
                                            padding="xs"
                                            withBorder
                                            style={{
                                                cursor: isReady ? 'pointer' : undefined,
                                                borderColor: isReady
                                                    ? 'var(--mantine-color-healthy-6)'
                                                    : undefined,
                                            }}
                                            onClick={
                                                isReady
                                                    ? () =>
                                                        handleDownload(
                                                            `/api/reports/${report.report_id}/download`,
                                                        )
                                                    : undefined
                                            }
                                        >
                                            <Group justify="space-between" wrap="nowrap">
                                                <Group gap="sm" wrap="nowrap">
                                                    <ThemeIcon
                                                        variant="light"
                                                        color={fmtMeta.color}
                                                        size="md"
                                                        radius="md"
                                                    >
                                                        <FmtIcon size={14}/>
                                                    </ThemeIcon>
                                                    <Stack gap={0}>
                                                        <Group gap={4}>
                                                            <Text size="sm" fw={500}>
                                                                {fmtMeta.label}
                                                            </Text>
                                                            <Badge
                                                                size="xs"
                                                                variant="outline"
                                                                color="gray"
                                                            >
                                                                {report.report_type}
                                                            </Badge>
                                                        </Group>
                                                        <Text size="xs" c="dimmed">
                                                            {formatDateTime(report.created_at)}
                                                        </Text>
                                                    </Stack>
                                                </Group>
                                                <Group gap={4}>
                                                    <Badge
                                                        color={STATUS_COLOR[report.status]}
                                                        variant="light"
                                                        size="sm"
                                                        leftSection={<StatusIcon size={10}/>}
                                                    >
                                                        {STATUS_LABEL[report.status]}
                                                    </Badge>
                                                    {isReady && (
                                                        <Tooltip label="Скачать">
                                                            <ActionIcon
                                                                variant="light"
                                                                color="green"
                                                                size="sm"
                                                            >
                                                                <IconDownload size={14}/>
                                                            </ActionIcon>
                                                        </Tooltip>
                                                    )}
                                                    {report.status === 'processing' && (
                                                        <Loader size={14}/>
                                                    )}
                                                </Group>
                                            </Group>
                                        </Card>
                                    );
                                })}
                            </Stack>
                        )}
                    </Card>
                </Grid.Col>
            </Grid>
        </Stack>
    );
}
