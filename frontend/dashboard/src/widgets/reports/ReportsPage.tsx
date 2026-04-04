'use client';

import { useCallback, useState } from 'react';
import {
    Badge,
    Button,
    Card,
    Center,
    Group,
    Loader,
    SegmentedControl,
    SimpleGrid,
    Stack,
    Table,
    Text,
    ThemeIcon,
    Title,
    ActionIcon,
    Tooltip,
    Alert,
    Progress,
} from '@mantine/core';
import { DateInput } from '@mantine/dates';
import {
    IconDownload,
    IconRefresh,
    IconFileText,
    IconFileSpreadsheet,
    IconFileTypePdf,
    IconAlertCircle,
    IconCheck,
    IconClock,
    IconLoader,
} from '@tabler/icons-react';
import { useGetReportsQuery, useReportGeneration } from '@/features/reports';
import { LocomotiveSelect } from '@/features/locomotives';
import { formatDateTime, dayjs } from '@/shared/utils/date';
import { useAppSelector } from '@/store/hooks';
import { selectAccessToken } from '@/store/authSlice';
import type { ReportFormat, ReportStatus } from '@/features/reports/types';

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

const FORMAT_ICON: Record<ReportFormat, typeof IconFileText> = {
    pdf: IconFileTypePdf,
    csv: IconFileSpreadsheet,
    json: IconFileText,
};

const FORMAT_COLORS: Record<ReportFormat, string> = {
    pdf: 'critical',
    csv: 'healthy',
    json: 'ktzBlue',
};

export function ReportsPage() {
    const token = useAppSelector(selectAccessToken);
    const [locomotiveId, setLocomotiveId] = useState<string | null>(null);
    const [format, setFormat] = useState<ReportFormat>('pdf');
    const [startDate, setStartDate] = useState<string | null>(null);
    const [endDate, setEndDate] = useState<string | null>(null);

    const { data: reports = [] } = useGetReportsQuery({});
    const { generate, status, isGenerating, downloadUrl, reset } = useReportGeneration();

    const handleDownload = useCallback(
        async (url: string) => {
            const res = await fetch(url, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
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

    const handleReset = () => {
        setLocomotiveId(null);
        setFormat('pdf');
        setStartDate(null);
        setEndDate(null);
        reset();
    };

    const FormatIcon = FORMAT_ICON[format];

    return (
        <Stack gap="lg">
            <Title order={3}>Отчёты</Title>

            {/* Report generation card */}
            <Card padding="lg" withBorder>
                <Stack gap="md">
                    <Group gap="xs">
                        <ThemeIcon variant="light" color="ktzBlue" size="md">
                            <IconFileText size={18} />
                        </ThemeIcon>
                        <Text fw={600} size="lg">Генерация отчёта</Text>
                    </Group>

                    <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
                        <LocomotiveSelect
                            label="Локомотив"
                            value={locomotiveId}
                            onChange={setLocomotiveId}
                            allowAll
                            w="100%"
                        />
                        <DateInput
                            label="Дата начала"
                            placeholder="Выберите дату"
                            value={startDate}
                            onChange={setStartDate}
                        />
                        <DateInput
                            label="Дата окончания"
                            placeholder="Выберите дату"
                            value={endDate}
                            onChange={setEndDate}
                        />
                    </SimpleGrid>

                    {!locomotiveId && (
                        <Alert color="ktzGold" variant="light" icon={<IconAlertCircle size={16} />}>
                            Без выбора локомотива будет сгенерирован сводный отчёт по парку. Данные агрегируются — это может занять время.
                        </Alert>
                    )}

                    <Group>
                        <Text size="sm" fw={500}>Формат:</Text>
                        <SegmentedControl
                            value={format}
                            onChange={(val) => setFormat(val as ReportFormat)}
                            data={[
                                { label: 'PDF', value: 'pdf' },
                                { label: 'CSV', value: 'csv' },
                                { label: 'JSON', value: 'json' },
                            ]}
                        />
                        <ThemeIcon variant="light" color={FORMAT_COLORS[format]} size="sm">
                            <FormatIcon size={14} />
                        </ThemeIcon>
                    </Group>

                    <Group>
                        <Button
                            onClick={handleGenerate}
                            loading={isGenerating}
                            disabled={!startDate || !endDate}
                            leftSection={<FormatIcon size={16} />}
                        >
                            Сгенерировать
                        </Button>
                        <Button
                            variant="subtle"
                            onClick={handleReset}
                            leftSection={<IconRefresh size={16} />}
                        >
                            Сбросить
                        </Button>
                    </Group>

                    {/* Generation progress */}
                    {isGenerating && (
                        <Card withBorder padding="sm" style={{ borderColor: 'var(--mantine-color-ktzBlue-5)' }}>
                            <Group gap="sm">
                                <Loader size="sm" />
                                <Stack gap={2} style={{ flex: 1 }}>
                                    <Text size="sm" fw={500}>Генерация отчёта...</Text>
                                    <Progress value={100} size="xs" animated color="ktzBlue" />
                                </Stack>
                            </Group>
                        </Card>
                    )}

                    {status === 'completed' && downloadUrl && (
                        <Card withBorder padding="sm" style={{ borderColor: 'var(--mantine-color-healthy-5)' }}>
                            <Group justify="space-between">
                                <Group gap="sm">
                                    <ThemeIcon variant="filled" color="green" size="md" radius="xl">
                                        <IconCheck size={16} />
                                    </ThemeIcon>
                                    <Stack gap={0}>
                                        <Text size="sm" fw={600}>Отчёт готов</Text>
                                        <Text size="xs" c="dimmed">Формат: {format.toUpperCase()}</Text>
                                    </Stack>
                                </Group>
                                <Button
                                    variant="filled"
                                    color="green"
                                    leftSection={<IconDownload size={16} />}
                                    onClick={() => handleDownload(downloadUrl)}
                                >
                                    Скачать
                                </Button>
                            </Group>
                        </Card>
                    )}

                    {status === 'failed' && (
                        <Alert color="red" variant="light" icon={<IconAlertCircle size={16} />} title="Ошибка генерации">
                            Не удалось сгенерировать отчёт. Попробуйте уменьшить диапазон дат или выбрать конкретный локомотив.
                        </Alert>
                    )}
                </Stack>
            </Card>

            {/* Report history */}
            <Card padding="lg" withBorder>
                <Stack gap="md">
                    <Group gap="xs">
                        <ThemeIcon variant="light" color="ktzCyan" size="md">
                            <IconClock size={18} />
                        </ThemeIcon>
                        <Text fw={600} size="lg">История отчётов</Text>
                        <Badge size="sm" variant="light" color="gray">
                            {reports.length}
                        </Badge>
                    </Group>

                    {reports.length === 0 ? (
                        <Center py="xl">
                            <Stack align="center" gap="xs">
                                <ThemeIcon variant="light" color="gray" size="xl" radius="xl">
                                    <IconFileText size={24} />
                                </ThemeIcon>
                                <Text c="dimmed" size="sm">Нет сгенерированных отчётов</Text>
                                <Text c="dimmed" size="xs">Создайте первый отчёт выше</Text>
                            </Stack>
                        </Center>
                    ) : (
                        <Table striped highlightOnHover verticalSpacing="sm">
                            <Table.Thead>
                                <Table.Tr>
                                    <Table.Th>Дата создания</Table.Th>
                                    <Table.Th>Тип</Table.Th>
                                    <Table.Th>Формат</Table.Th>
                                    <Table.Th>Статус</Table.Th>
                                    <Table.Th style={{ textAlign: 'right' }}>Действие</Table.Th>
                                </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                                {reports.map((report) => {
                                    const StatusIcon = STATUS_ICON[report.status];
                                    const FmtIcon = FORMAT_ICON[report.format] ?? IconFileText;

                                    return (
                                        <Table.Tr key={report.report_id}>
                                            <Table.Td>
                                                <Text size="sm">{formatDateTime(report.created_at)}</Text>
                                            </Table.Td>
                                            <Table.Td>
                                                <Badge size="xs" variant="outline" color="gray">
                                                    {report.report_type}
                                                </Badge>
                                            </Table.Td>
                                            <Table.Td>
                                                <Group gap={4}>
                                                    <FmtIcon size={14} />
                                                    <Text size="sm" fw={500}>
                                                        {report.format.toUpperCase()}
                                                    </Text>
                                                </Group>
                                            </Table.Td>
                                            <Table.Td>
                                                <Badge
                                                    color={STATUS_COLOR[report.status]}
                                                    variant="light"
                                                    leftSection={<StatusIcon size={12} />}
                                                >
                                                    {STATUS_LABEL[report.status]}
                                                </Badge>
                                            </Table.Td>
                                            <Table.Td style={{ textAlign: 'right' }}>
                                                {report.status === 'completed' ? (
                                                    <Tooltip label="Скачать отчёт">
                                                        <ActionIcon
                                                            variant="light"
                                                            color="green"
                                                            onClick={() =>
                                                                handleDownload(
                                                                    `/api/reports/${report.report_id}/download`,
                                                                )
                                                            }
                                                        >
                                                            <IconDownload size={16} />
                                                        </ActionIcon>
                                                    </Tooltip>
                                                ) : report.status === 'processing' ? (
                                                    <Loader size="xs" />
                                                ) : (
                                                    <Text size="sm" c="dimmed">—</Text>
                                                )}
                                            </Table.Td>
                                        </Table.Tr>
                                    );
                                })}
                            </Table.Tbody>
                        </Table>
                    )}
                </Stack>
            </Card>
        </Stack>
    );
}
