'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
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
} from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { useLoginMutation } from '@/features/auth';
import { useAppDispatch } from '@/store/hooks';
import { setCredentials } from '@/store/authSlice';

export function LoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [login, { isLoading }] = useLoginMutation();
    const dispatch = useAppDispatch();
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        try {
            const result = await login({ username, password }).unwrap();
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
            }}
        >
            <Card
                w={400}
                padding="xl"
                shadow="lg"
                style={{
                    borderTop: '3px solid var(--mantine-color-ktzGold-5)',
                }}
            >
                <Stack gap="lg">
                    <Center>
                        <Text
                            size="xl"
                            fw={700}
                            ff="var(--font-mono), monospace"
                            c="var(--mantine-color-ktzGold-5)"
                        >
                            КТЖ
                        </Text>
                    </Center>
                    <Text ta="center" size="sm" c="var(--dashboard-text-secondary)">
                        Цифровой двойник локомотива
                    </Text>

                    {error && (
                        <Alert color="red" variant="light" icon={<IconAlertCircle size={16} />}>
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
                            />
                            <PasswordInput
                                label="Пароль"
                                placeholder="Введите пароль"
                                value={password}
                                onChange={(e) => setPassword(e.currentTarget.value)}
                                required
                            />
                            <Button type="submit" fullWidth loading={isLoading} mt="sm">
                                Войти
                            </Button>
                        </Stack>
                    </form>
                </Stack>
            </Card>
        </Box>
    );
}
