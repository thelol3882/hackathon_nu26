'use client';

import { Provider as ReduxProvider } from 'react-redux';
import { MantineProvider } from '@mantine/core';
import { ModalsProvider } from '@mantine/modals';
import { Notifications } from '@mantine/notifications';
import { store } from '@/store/store';
import { theme, cssVariablesResolver } from '@/theme/theme';

export function Providers({ children }: { children: React.ReactNode }) {
    return (
        <ReduxProvider store={store}>
            <MantineProvider
                theme={theme}
                defaultColorScheme="dark"
                cssVariablesResolver={cssVariablesResolver}
            >
                <ModalsProvider>
                    <Notifications position="top-right" />
                    {children}
                </ModalsProvider>
            </MantineProvider>
        </ReduxProvider>
    );
}
