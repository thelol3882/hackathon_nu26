'use client';

import {useState} from 'react';
import {useRouter} from 'next/navigation';
import {
    Card,
    TextInput,
    PasswordInput,
    Button,
    Stack,
    Text,
    Center,
    Box,
    Alert,
    Group,
    ThemeIcon,
    Divider,
} from '@mantine/core';
import {IconAlertCircle, IconTrain, IconShieldCheck} from '@tabler/icons-react';
import {useLoginMutation} from '@/features/auth';
import {useAppDispatch} from '@/store/hooks';
import {setCredentials} from '@/store/authSlice';

export function LoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [login, {isLoading}] = useLoginMutation();
    const dispatch = useAppDispatch();
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        try {
            const result = await login({username, password}).unwrap();
            dispatch(
                setCredentials({
                    access_token: result.access_token,
                    username,
                }),
            );
            router.push('/dashboard');
        } catch {
            setError('Неверное имя пользователя или пароль');
        }
    };

    return (
        <Box
            style={{
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'var(--dashboard-bg)',
                position: 'relative',
                overflow: 'hidden',
            }}
        >
            <Box
                style={{
                    position: 'absolute',
                    top: '-20%',
                    right: '-10%',
                    width: '50vw',
                    height: '50vw',
                    borderRadius: '50%',
                    background: 'radial-gradient(circle, rgba(3,136,230,0.08) 0%, transparent 70%)',
                    pointerEvents: 'none',
                }}
            />
            <Box
                style={{
                    position: 'absolute',
                    bottom: '-30%',
                    left: '-15%',
                    width: '60vw',
                    height: '60vw',
                    borderRadius: '50%',
                    background: 'radial-gradient(circle, rgba(254,198,4,0.05) 0%, transparent 70%)',
                    pointerEvents: 'none',
                }}
            />

            <Card
                w={420}
                padding="xl"
                shadow="xl"
                style={{
                    borderTop: '3px solid var(--mantine-color-ktzBlue-5)',
                    position: 'relative',
                    zIndex: 1,
                }}
            >
                <Stack gap="lg">
                    <Center>
                        <Stack align="center" gap={8}>
                            <ThemeIcon size={56} radius="xl" variant="light" color="ktzBlue">
                                <IconTrain size={28} stroke={1.5}/>
                            </ThemeIcon>
                            <Text
                                size="xl"
                                fw={700}
                                ff="var(--font-mono), monospace"
                                c="var(--mantine-color-ktzBlue-5)"
                            >
                                КТЖ
                            </Text>
                        </Stack>
                    </Center>

                    <Stack align="center" gap={2}>
                        <Text size="lg" fw={600} c="var(--dashboard-text-primary)">
                            Цифровой двойник
                        </Text>
                        <Text size="sm" c="var(--dashboard-text-secondary)">
                            Система мониторинга локомотивов
                        </Text>
                    </Stack>

                    <Divider
                        label={
                            <Group gap={4}>
                                <IconShieldCheck size={14}/>
                                <Text size="xs">Авторизация</Text>
                            </Group>
                        }
                        labelPosition="center"
                    />

                    {error && (
                        <Alert color="red" variant="light" icon={<IconAlertCircle size={16}/>}>
                            {error}
                        </Alert>
                    )}

                    <form onSubmit={handleSubmit}>
                        <Stack gap="md">
                            <TextInput
                                label="Имя пользователя"
                                placeholder="Введите имя"
                                value={username}
                                onChange={(e) => setUsername(e.currentTarget.value)}
                                required
                                size="md"
                            />
                            <PasswordInput
                                label="Пароль"
                                placeholder="Введите пароль"
                                value={password}
                                onChange={(e) => setPassword(e.currentTarget.value)}
                                required
                                size="md"
                            />
                            <Button type="submit" fullWidth loading={isLoading} mt="sm" size="md">
                                Войти в систему
                            </Button>
                        </Stack>
                    </form>

                    <Text size="xs" c="dimmed" ta="center">
                        Защищённое подключение
                    </Text>
                </Stack>
            </Card>
        </Box>
    );
}
