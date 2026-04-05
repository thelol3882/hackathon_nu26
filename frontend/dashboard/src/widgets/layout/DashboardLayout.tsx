'use client';

import {type ReactNode} from 'react';
import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {
    AppShell,
    Burger,
    Group,
    NavLink,
    Text,
    Tooltip,
    ActionIcon,
    Box,
    Stack,
    Badge,
    Divider,
    useMantineColorScheme,
} from '@mantine/core';
import {useDisclosure} from '@mantine/hooks';
import {IconSun, IconMoon, IconLogout, IconTrain} from '@tabler/icons-react';
import {useAppSelector, useAppDispatch} from '@/store/hooks';
import {selectIsAdmin, selectUsername, selectRole, logout} from '@/store/authSlice';
import {LocomotiveSelect} from '@/features/locomotives';
import {navigationItems} from './navigation';
import {LocomotiveProvider, useLocomotive} from './LocomotiveContext';

function LocomotiveSelector() {
    const {locomotiveId, setLocomotive} = useLocomotive();
    return <LocomotiveSelect value={locomotiveId} onChange={setLocomotive}/>;
}

export function DashboardLayout({children}: { children: ReactNode }) {
    const [opened, {toggle}] = useDisclosure(true);
    const pathname = usePathname();
    const isAdmin = useAppSelector(selectIsAdmin);
    const username = useAppSelector(selectUsername);
    const role = useAppSelector(selectRole);
    const dispatch = useAppDispatch();
    const {colorScheme, toggleColorScheme} = useMantineColorScheme();

    const visibleNavItems = navigationItems.filter((item) => !item.adminOnly || isAdmin);

    return (
        <LocomotiveProvider>
            <AppShell
                header={{height: 56}}
                navbar={{
                    width: 240,
                    breakpoint: 'sm',
                    collapsed: {mobile: !opened, desktop: !opened},
                }}
                padding="md"
            >
                <AppShell.Header
                    style={{
                        borderBottom: '1px solid var(--dashboard-border)',
                        backgroundColor: 'var(--dashboard-surface)',
                    }}
                >
                    <Group h="100%" px="md" justify="space-between">
                        <Group gap="sm">
                            <Burger opened={opened} onClick={toggle} size="sm"/>
                            <Group gap={6} visibleFrom="sm">
                                <IconTrain
                                    size={20}
                                    style={{color: 'var(--mantine-color-ktzBlue-5)'}}
                                />
                                <Text
                                    fw={700}
                                    size="md"
                                    ff="var(--font-mono), monospace"
                                    c="var(--mantine-color-ktzBlue-5)"
                                >
                                    КТЖ
                                </Text>
                            </Group>
                        </Group>

                        <Group gap="md">
                            <LocomotiveSelector/>
                            <ActionIcon
                                variant="subtle"
                                size="md"
                                onClick={toggleColorScheme}
                                aria-label="Переключить тему"
                            >
                                {colorScheme === 'dark' ? (
                                    <IconSun size={16} stroke={1.5}/>
                                ) : (
                                    <IconMoon size={16} stroke={1.5}/>
                                )}
                            </ActionIcon>
                        </Group>
                    </Group>
                </AppShell.Header>

                <AppShell.Navbar
                    p="sm"
                    style={{
                        backgroundColor: 'var(--dashboard-surface)',
                        borderRight: '1px solid var(--dashboard-border)',
                    }}
                >
                    <AppShell.Section grow>
                        <Stack gap={2}>
                            {visibleNavItems.map((item) => (
                                <NavLink
                                    key={item.key}
                                    component={Link}
                                    href={item.href}
                                    label={item.label}
                                    leftSection={<item.icon size={18} stroke={1.5}/>}
                                    active={pathname === item.href}
                                    variant="light"
                                    style={{borderRadius: 'var(--mantine-radius-md)'}}
                                />
                            ))}
                        </Stack>
                    </AppShell.Section>

                    <AppShell.Section>
                        <Divider mb="sm"/>
                        <Box
                            p="xs"
                            style={{
                                borderRadius: 'var(--mantine-radius-md)',
                                backgroundColor: 'var(--dashboard-surface-elevated)',
                            }}
                        >
                            <Group justify="space-between">
                                <Stack gap={0}>
                                    <Text size="sm" fw={500} truncate>
                                        {username ?? 'Гость'}
                                    </Text>
                                    <Badge
                                        size="xs"
                                        variant="light"
                                        color={role === 'admin' ? 'ktzGold' : 'ktzBlue'}
                                    >
                                        {role === 'admin' ? 'Администратор' : 'Оператор'}
                                    </Badge>
                                </Stack>
                                <Tooltip label="Выйти">
                                    <ActionIcon
                                        variant="subtle"
                                        size="md"
                                        color="red"
                                        onClick={() => dispatch(logout())}
                                        aria-label="Выйти"
                                    >
                                        <IconLogout size={16} stroke={1.5}/>
                                    </ActionIcon>
                                </Tooltip>
                            </Group>
                        </Box>
                    </AppShell.Section>
                </AppShell.Navbar>

                <AppShell.Main style={{backgroundColor: 'var(--dashboard-bg)'}}>
                    {children}
                </AppShell.Main>
            </AppShell>
        </LocomotiveProvider>
    );
}
