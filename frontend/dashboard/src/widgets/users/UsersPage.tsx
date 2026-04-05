'use client';

import {useState} from 'react';
import {
    Alert,
    Badge,
    Button,
    Card,
    Center,
    Group,
    Loader,
    PasswordInput,
    Select,
    SimpleGrid,
    Stack,
    Table,
    Text,
    TextInput,
    ThemeIcon,
    Title,
} from '@mantine/core';
import {showNotification} from '@mantine/notifications';
import {
    IconAlertCircle,
    IconCheck,
    IconShieldCheck,
    IconUser,
    IconUserPlus,
    IconUsers,
} from '@tabler/icons-react';
import {useGetUsersQuery, useRegisterMutation} from '@/features/auth';
import {useAppSelector} from '@/store/hooks';
import {selectIsAdmin} from '@/store/authSlice';
import {formatDateTime} from '@/shared/utils/date';

export function UsersPage() {
    const isAdmin = useAppSelector(selectIsAdmin);
    const {data, isLoading} = useGetUsersQuery(undefined, {skip: !isAdmin});
    const [register, {isLoading: isRegistering}] = useRegisterMutation();
    const users = data?.users ?? [];
    const total = data?.total ?? 0;

    const [newUsername, setNewUsername] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newRole, setNewRole] = useState<string>('operator');
    const [formError, setFormError] = useState<string | null>(null);

    if (!isAdmin) {
        return (
            <Center h="50vh">
                <Stack align="center" gap="md">
                    <ThemeIcon size={64} radius="xl" variant="light" color="red">
                        <IconAlertCircle size={32}/>
                    </ThemeIcon>
                    <Text size="lg" fw={600}>
                        Доступ запрещён
                    </Text>
                    <Text size="sm" c="dimmed" ta="center" maw={300}>
                        Управление пользователями доступно только администраторам
                    </Text>
                </Stack>
            </Center>
        );
    }

    const handleCreate = async () => {
        setFormError(null);
        if (!newUsername.trim() || !newPassword.trim()) {
            setFormError('Заполните все поля');
            return;
        }
        if (newPassword.length < 4) {
            setFormError('Пароль должен быть не менее 4 символов');
            return;
        }
        try {
            await register({
                username: newUsername.trim(),
                password: newPassword,
                role: newRole,
            }).unwrap();
            showNotification({
                title: 'Пользователь создан',
                message: `${newUsername} (${newRole === 'admin' ? 'администратор' : 'оператор'})`,
                color: 'green',
                icon: <IconCheck size={16}/>,
            });
            setNewUsername('');
            setNewPassword('');
            setNewRole('operator');
        } catch {
            setFormError('Не удалось создать пользователя. Возможно, логин уже занят.');
        }
    };

    return (
        <Stack gap="lg">
            <Group justify="space-between">
                <Group gap="sm">
                    <ThemeIcon variant="light" color="ktzBlue" size="lg">
                        <IconUsers size={20}/>
                    </ThemeIcon>
                    <Title order={3}>Пользователи</Title>
                </Group>
                <Badge
                    color="ktzGold"
                    variant="light"
                    size="lg"
                    leftSection={<IconShieldCheck size={12}/>}
                >
                    Администратор
                </Badge>
            </Group>

            <SimpleGrid cols={{base: 1, sm: 3}}>
                <Card padding="md" withBorder>
                    <Group gap="sm">
                        <ThemeIcon variant="light" color="ktzBlue" size="lg">
                            <IconUsers size={20}/>
                        </ThemeIcon>
                        <div>
                            <Text size="xs" c="dimmed">
                                Всего пользователей
                            </Text>
                            <Text size="xl" fw={700} ff="var(--font-mono), monospace">
                                {total}
                            </Text>
                        </div>
                    </Group>
                </Card>
                <Card padding="md" withBorder>
                    <Group gap="sm">
                        <ThemeIcon variant="light" color="ktzGold" size="lg">
                            <IconShieldCheck size={20}/>
                        </ThemeIcon>
                        <div>
                            <Text size="xs" c="dimmed">
                                Администраторы
                            </Text>
                            <Text size="xl" fw={700} ff="var(--font-mono), monospace">
                                {users.filter((u) => u.role === 'admin').length}
                            </Text>
                        </div>
                    </Group>
                </Card>
                <Card padding="md" withBorder>
                    <Group gap="sm">
                        <ThemeIcon variant="light" color="healthy" size="lg">
                            <IconUser size={20}/>
                        </ThemeIcon>
                        <div>
                            <Text size="xs" c="dimmed">
                                Операторы
                            </Text>
                            <Text size="xl" fw={700} ff="var(--font-mono), monospace">
                                {users.filter((u) => u.role === 'operator').length}
                            </Text>
                        </div>
                    </Group>
                </Card>
            </SimpleGrid>

            <Card padding="lg" withBorder>
                <Group gap="xs" mb="md">
                    <ThemeIcon variant="light" color="ktzBlue" size="md">
                        <IconUserPlus size={16}/>
                    </ThemeIcon>
                    <Text fw={600} size="lg">
                        Создать пользователя
                    </Text>
                </Group>
                {formError && (
                    <Alert color="red" variant="light" icon={<IconAlertCircle size={14}/>} mb="md">
                        {formError}
                    </Alert>
                )}
                <Group grow align="flex-end">
                    <TextInput
                        label="Логин"
                        placeholder="ivanov"
                        value={newUsername}
                        onChange={(e) => setNewUsername(e.currentTarget.value)}
                    />
                    <PasswordInput
                        label="Пароль"
                        placeholder="Минимум 4 символа"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.currentTarget.value)}
                    />
                    <Select
                        label="Роль"
                        data={[
                            {value: 'operator', label: 'Оператор (машинист/диспетчер)'},
                            {value: 'admin', label: 'Администратор'},
                        ]}
                        value={newRole}
                        onChange={(v) => v && setNewRole(v)}
                    />
                    <Button
                        leftSection={<IconUserPlus size={16}/>}
                        onClick={handleCreate}
                        loading={isRegistering}
                    >
                        Создать
                    </Button>
                </Group>
            </Card>

            <Card padding="lg" withBorder>
                <Text fw={600} size="lg" mb="md">
                    Все пользователи
                </Text>

                {isLoading ? (
                    <Center py="xl">
                        <Loader size="md"/>
                    </Center>
                ) : users.length === 0 ? (
                    <Center py="xl">
                        <Stack align="center" gap="xs">
                            <ThemeIcon variant="light" color="gray" size="xl" radius="xl">
                                <IconUsers size={24}/>
                            </ThemeIcon>
                            <Text c="dimmed">Нет пользователей</Text>
                        </Stack>
                    </Center>
                ) : (
                    <Table striped highlightOnHover verticalSpacing="sm">
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th>Пользователь</Table.Th>
                                <Table.Th>Роль</Table.Th>
                                <Table.Th>Дата создания</Table.Th>
                                <Table.Th>ID</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {users.map((user) => (
                                <Table.Tr key={user.id}>
                                    <Table.Td>
                                        <Group gap="sm">
                                            <ThemeIcon
                                                variant="light"
                                                color={
                                                    user.role === 'admin' ? 'ktzGold' : 'ktzBlue'
                                                }
                                                size="md"
                                                radius="xl"
                                            >
                                                {user.role === 'admin' ? (
                                                    <IconShieldCheck size={14}/>
                                                ) : (
                                                    <IconUser size={14}/>
                                                )}
                                            </ThemeIcon>
                                            <Text size="sm" fw={500}>
                                                {user.username}
                                            </Text>
                                        </Group>
                                    </Table.Td>
                                    <Table.Td>
                                        <Badge
                                            variant="light"
                                            color={user.role === 'admin' ? 'ktzGold' : 'ktzBlue'}
                                        >
                                            {user.role === 'admin' ? 'Администратор' : 'Оператор'}
                                        </Badge>
                                    </Table.Td>
                                    <Table.Td>
                                        <Text size="sm" c="dimmed">
                                            {user.created_at
                                                ? formatDateTime(user.created_at)
                                                : '—'}
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
            </Card>
        </Stack>
    );
}
