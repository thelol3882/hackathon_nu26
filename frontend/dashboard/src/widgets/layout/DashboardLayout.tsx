'use client';

import { type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
    AppShell,
    Burger,
    Group,
    NavLink,
    Select,
    Text,
    Tooltip,
    ActionIcon,
    Box,
    useMantineColorScheme,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconSun, IconMoon, IconLogout } from '@tabler/icons-react';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { selectIsAdmin, selectUsername, logout } from '@/store/authSlice';
import { useGetLocomotivesQuery } from '@/features/locomotives';
import { navigationItems } from './navigation';
import { LocomotiveProvider, useLocomotive } from './LocomotiveContext';

function LocomotiveSelector() {
    const { locomotiveId, setLocomotiveId } = useLocomotive();
    const { data: locomotives = [], isLoading } = useGetLocomotivesQuery({});

    const options = locomotives.map((loco) => ({
        value: loco.id,
        label: `${loco.model} — ${loco.serial_number}`,
    }));

    return (
        <Select
            placeholder="Выберите локомотив"
            data={options}
            value={locomotiveId}
            onChange={setLocomotiveId}
            searchable
            clearable
            disabled={isLoading}
            w={280}
        />
    );
}

function ConnectionStatus() {
    const { locomotiveId } = useLocomotive();
    const connected = !!locomotiveId;
    const color = connected ? 'var(--mantine-color-green-5)' : 'var(--mantine-color-gray-5)';
    const label = connected ? 'Подключено' : 'Не подключено';

    return (
        <Tooltip label={label}>
            <Box
                style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: color,
                    flexShrink: 0,
                }}
            />
        </Tooltip>
    );
}

export function DashboardLayout({ children }: { children: ReactNode }) {
    const [opened, { toggle }] = useDisclosure(true);
    const pathname = usePathname();
    const isAdmin = useAppSelector(selectIsAdmin);
    const username = useAppSelector(selectUsername);
    const dispatch = useAppDispatch();
    const { colorScheme, toggleColorScheme } = useMantineColorScheme();

    const visibleNavItems = navigationItems.filter((item) => !item.adminOnly || isAdmin);

    return (
        <LocomotiveProvider>
            <AppShell
                header={{ height: 60 }}
                navbar={{
                    width: 260,
                    breakpoint: 'sm',
                    collapsed: { mobile: !opened, desktop: !opened },
                }}
                padding="md"
            >
                {/* Header */}
                <AppShell.Header>
                    <Group h="100%" px="md" justify="space-between">
                        <Group>
                            <Burger opened={opened} onClick={toggle} size="sm" />
                            <Text
                                fw={700}
                                size="lg"
                                ff="var(--font-mono), monospace"
                                visibleFrom="sm"
                            >
                                КТЖ
                            </Text>
                        </Group>

                        <Group gap="md">
                            <LocomotiveSelector />
                            <ConnectionStatus />
                            <ActionIcon
                                variant="subtle"
                                size="lg"
                                onClick={toggleColorScheme}
                                aria-label="Переключить тему"
                            >
                                {colorScheme === 'dark' ? (
                                    <IconSun size={18} stroke={1.5} />
                                ) : (
                                    <IconMoon size={18} stroke={1.5} />
                                )}
                            </ActionIcon>
                            {username && (
                                <Text size="sm" c="dimmed">
                                    {username}
                                </Text>
                            )}
                            <Tooltip label="Выйти">
                                <ActionIcon
                                    variant="subtle"
                                    size="lg"
                                    color="red"
                                    onClick={() => dispatch(logout())}
                                    aria-label="Выйти"
                                >
                                    <IconLogout size={18} stroke={1.5} />
                                </ActionIcon>
                            </Tooltip>
                        </Group>
                    </Group>
                </AppShell.Header>

                {/* Navbar */}
                <AppShell.Navbar p="md" style={{ backgroundColor: 'var(--dashboard-surface)' }}>
                    <AppShell.Section grow>
                        {visibleNavItems.map((item) => (
                            <NavLink
                                key={item.key}
                                component={Link}
                                href={item.href}
                                label={item.label}
                                leftSection={<item.icon size={20} stroke={1.5} />}
                                active={pathname === item.href}
                                mb={4}
                            />
                        ))}
                    </AppShell.Section>
                </AppShell.Navbar>

                {/* Main content */}
                <AppShell.Main>{children}</AppShell.Main>
            </AppShell>
        </LocomotiveProvider>
    );
}
