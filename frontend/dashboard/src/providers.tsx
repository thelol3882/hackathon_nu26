'use client';

import {useEffect} from 'react';
import {Provider as ReduxProvider} from 'react-redux';
import {MantineProvider} from '@mantine/core';
import {ModalsProvider} from '@mantine/modals';
import {Notifications} from '@mantine/notifications';
import {DatesProvider} from '@mantine/dates';
import 'dayjs/locale/ru';
import {store} from '@/store/store';
import {hydrateAuth} from '@/store/authSlice';
import {theme, cssVariablesResolver} from '@/theme/theme';

function AuthHydrator({children}: { children: React.ReactNode }) {
    useEffect(() => {
        store.dispatch(hydrateAuth());
    }, []);
    return children;
}

export function Providers({children}: { children: React.ReactNode }) {
    return (
        <ReduxProvider store={store}>
            <AuthHydrator>
                <MantineProvider
                    theme={theme}
                    defaultColorScheme="dark"
                    cssVariablesResolver={cssVariablesResolver}
                >
                    <DatesProvider settings={{locale: 'ru'}}>
                        <ModalsProvider>
                            <Notifications position="top-right"/>
                            {children}
                        </ModalsProvider>
                    </DatesProvider>
                </MantineProvider>
            </AuthHydrator>
        </ReduxProvider>
    );
}
