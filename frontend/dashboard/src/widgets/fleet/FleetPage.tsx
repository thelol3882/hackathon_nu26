'use client';

import {
    Badge,
    Box,
    Card,
    Group,
    Progress,
    SimpleGrid,
    Stack,
    Table,
    Text,
    ThemeIcon,
    Title,
} from '@mantine/core';
import {
    IconBroadcast,
    IconBroadcastOff,
    IconAlertTriangle,
    IconCheck,
    IconFlame,
    IconTrain,
} from '@tabler/icons-react';
import { useFleetDispatch } from '@/shared/ws/useFleetDispatch';
import { useAppSelector } from '@/store/hooks';
import {
    selectFleetCategories,
    selectFleetAvgScore,
    selectFleetSize,
    selectWorst10,
    selectFleetLastUpdated,
} from '@/store/slices/fleetSlice';
import { getRelativeTime } from '@/shared/utils/date';

/* ------------------------------------------------------------------ */
/*  Category stat card                                                 */
/* ------------------------------------------------------------------ */

function CategoryCard({
    label,
    count,
    total,
    color,
    icon,
}: {
    label: string;
    count: number;
    total: number;
    color: string;
    icon: React.ReactNode;
}) {
    const pct = total > 0 ? Math.round((count / total) * 100) : 0;
    return (
        <Card withBorder padding="lg" radius="md">
            <Group justify="space-between" mb="xs">
                <Text size="sm" c="dimmed" fw={500}>
                    {label}
                </Text>
                <ThemeIcon variant="light" color={color} size="lg" radius="md">
                    {icon}
                </ThemeIcon>
            </Group>
            <Text size="xl" fw={700}>
                {count}
            </Text>
            <Progress value={pct} color={color} size="sm" mt="sm" radius="xl" />
            <Text size="xs" c="dimmed" mt={4}>
                {pct}% of fleet
            </Text>
        </Card>
    );
}

/* ------------------------------------------------------------------ */
/*  Worst-10 table                                                     */
/* ------------------------------------------------------------------ */

function WorstTable() {
    const worst10 = useAppSelector(selectWorst10);

    if (worst10.length === 0) {
        return (
            <Text size="sm" c="dimmed" ta="center" py="xl">
                No data yet
            </Text>
        );
    }

    return (
        <Table striped highlightOnHover>
            <Table.Thead>
                <Table.Tr>
                    <Table.Th>#</Table.Th>
                    <Table.Th>Locomotive</Table.Th>
                    <Table.Th>Type</Table.Th>
                    <Table.Th ta="right">Score</Table.Th>
                    <Table.Th>Category</Table.Th>
                </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
                {worst10.map((loco, i) => (
                    <Table.Tr key={loco.locomotive_id}>
                        <Table.Td>{i + 1}</Table.Td>
                        <Table.Td ff="monospace" fz="sm">
                            {loco.locomotive_id.slice(0, 12)}
                        </Table.Td>
                        <Table.Td>
                            <Badge variant="light" size="sm">
                                {loco.locomotive_type}
                            </Badge>
                        </Table.Td>
                        <Table.Td ta="right" fw={600} c={scoreColor(loco.score)}>
                            {loco.score.toFixed(1)}
                        </Table.Td>
                        <Table.Td>
                            <Badge color={categoryColor(loco.category)} variant="filled" size="sm">
                                {loco.category}
                            </Badge>
                        </Table.Td>
                    </Table.Tr>
                ))}
            </Table.Tbody>
        </Table>
    );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

export function FleetPage() {
    const { connectionStatus } = useFleetDispatch();
    const categories = useAppSelector(selectFleetCategories);
    const avgScore = useAppSelector(selectFleetAvgScore);
    const fleetSize = useAppSelector(selectFleetSize);
    const lastUpdated = useAppSelector(selectFleetLastUpdated);

    const connected = connectionStatus === 'connected';

    return (
        <Stack gap="md" p="md">
            {/* Header */}
            <Group justify="space-between">
                <Group gap="sm">
                    <IconTrain size={24} />
                    <Title order={3}>Fleet Overview</Title>
                    <Badge variant="light" size="lg">
                        {fleetSize} locomotives
                    </Badge>
                </Group>
                <Group gap="xs">
                    {connected ? (
                        <Badge leftSection={<IconBroadcast size={14} />} color="teal" variant="light">
                            Live
                        </Badge>
                    ) : (
                        <Badge leftSection={<IconBroadcastOff size={14} />} color="gray" variant="light">
                            {connectionStatus}
                        </Badge>
                    )}
                    {lastUpdated && (
                        <Text size="xs" c="dimmed">
                            {getRelativeTime(new Date(lastUpdated).toISOString())}
                        </Text>
                    )}
                </Group>
            </Group>

            {/* Average score */}
            <Card withBorder padding="lg" radius="md">
                <Group justify="space-between">
                    <Box>
                        <Text size="sm" c="dimmed" fw={500}>
                            Fleet Average Health
                        </Text>
                        <Text size="2rem" fw={700} c={scoreColor(avgScore)}>
                            {avgScore > 0 ? avgScore.toFixed(1) : '--'}
                        </Text>
                    </Box>
                    <Progress.Root size="xl" w={200}>
                        <Progress.Section value={categories.norma > 0 ? (categories.norma / Math.max(fleetSize, 1)) * 100 : 0} color="teal" />
                        <Progress.Section value={categories.vnimanie > 0 ? (categories.vnimanie / Math.max(fleetSize, 1)) * 100 : 0} color="yellow" />
                        <Progress.Section value={categories.kritichno > 0 ? (categories.kritichno / Math.max(fleetSize, 1)) * 100 : 0} color="red" />
                    </Progress.Root>
                </Group>
            </Card>

            {/* Category cards */}
            <SimpleGrid cols={{ base: 1, sm: 3 }}>
                <CategoryCard
                    label="Normal"
                    count={categories.norma}
                    total={fleetSize}
                    color="teal"
                    icon={<IconCheck size={20} />}
                />
                <CategoryCard
                    label="Warning"
                    count={categories.vnimanie}
                    total={fleetSize}
                    color="yellow"
                    icon={<IconAlertTriangle size={20} />}
                />
                <CategoryCard
                    label="Critical"
                    count={categories.kritichno}
                    total={fleetSize}
                    color="red"
                    icon={<IconFlame size={20} />}
                />
            </SimpleGrid>

            {/* Worst 10 */}
            <Card withBorder padding="lg" radius="md">
                <Title order={5} mb="sm">
                    Worst 10 Locomotives
                </Title>
                <WorstTable />
            </Card>
        </Stack>
    );
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function scoreColor(score: number): string {
    if (score >= 80) return 'teal';
    if (score >= 50) return 'yellow';
    return 'red';
}

function categoryColor(category: string): string {
    if (category === '\u041d\u043e\u0440\u043c\u0430') return 'teal'; // "Норма"
    if (category === '\u0412\u043d\u0438\u043c\u0430\u043d\u0438\u0435') return 'yellow'; // "Внимание"
    return 'red';
}
