'use client';

import { useCallback, useState } from 'react';
import {
    Card,
    SegmentedControl,
    Button,
    Group,
    Stack,
    Table,
    Badge,
    Loader,
    Text,
    ActionIcon,
    Title,
} from '@mantine/core';
import { DateInput } from '@mantine/dates';
import { IconDownload, IconRefresh } from '@tabler/icons-react';
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

    return (
        <Stack gap="lg">
            <Title order={3}>Отчёты</Title>

            <Card padding="lg" withBorder>
                <Stack gap="md">
                    <Text fw={600}>Генерация отчёта</Text>

                    <Group grow align="flex-end">
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
                    </Group>

                    <Group>
                        <Text size="sm" fw={500}>
                            Формат:
                        </Text>
                        <SegmentedControl
                            value={format}
                            onChange={(val) => setFormat(val as ReportFormat)}
                            data={[
                                { label: 'PDF', value: 'pdf' },
                                { label: 'CSV', value: 'csv' },
                                { label: 'JSON', value: 'json' },
                            ]}
                        />
                    </Group>

                    <Group>
                        <Button
                            onClick={handleGenerate}
                            loading={isGenerating}
                            disabled={!startDate || !endDate}
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

                    {isGenerating && (
                        <Group gap="sm">
                            <Loader size="sm" />
                            <Text size="sm" c="dimmed">
                                Генерация отчёта...
                            </Text>
                        </Group>
                    )}

                    {status === 'completed' && downloadUrl && (
                        <Button
                            variant="light"
                            color="green"
                            leftSection={<IconDownload size={16} />}
                            onClick={() => handleDownload(downloadUrl)}
                        >
                            Скачать отчёт
                        </Button>
                    )}

                    {status === 'failed' && (
                        <Text c="red" size="sm">
                            Ошибка при генерации отчёта
                        </Text>
                    )}
                </Stack>
            </Card>

            <Card padding="lg" withBorder>
                <Stack gap="md">
                    <Text fw={600}>История отчётов</Text>

                    <Table striped highlightOnHover>
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th>Дата</Table.Th>
                                <Table.Th>Тип</Table.Th>
                                <Table.Th>Формат</Table.Th>
                                <Table.Th>Статус</Table.Th>
                                <Table.Th>Действие</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {reports.map((report) => (
                                <Table.Tr key={report.report_id}>
                                    <Table.Td>{formatDateTime(report.created_at)}</Table.Td>
                                    <Table.Td>{report.report_type}</Table.Td>
                                    <Table.Td>{report.format.toUpperCase()}</Table.Td>
                                    <Table.Td>
                                        <Badge color={STATUS_COLOR[report.status]} variant="light">
                                            {STATUS_LABEL[report.status]}
                                        </Badge>
                                    </Table.Td>
                                    <Table.Td>
                                        {report.status === 'completed' ? (
                                            <ActionIcon
                                                variant="subtle"
                                                onClick={() =>
                                                    handleDownload(
                                                        `/api/reports/${report.report_id}/download`,
                                                    )
                                                }
                                            >
                                                <IconDownload size={16} />
                                            </ActionIcon>
                                        ) : (
                                            <Text size="sm" c="dimmed">
                                                —
                                            </Text>
                                        )}
                                    </Table.Td>
                                </Table.Tr>
                            ))}
                            {reports.length === 0 && (
                                <Table.Tr>
                                    <Table.Td colSpan={5}>
                                        <Text ta="center" c="dimmed" size="sm">
                                            Нет отчётов
                                        </Text>
                                    </Table.Td>
                                </Table.Tr>
                            )}
                        </Table.Tbody>
                    </Table>
                </Stack>
            </Card>
        </Stack>
    );
}
