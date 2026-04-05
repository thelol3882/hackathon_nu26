import React, { type PropsWithChildren } from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { Provider } from 'react-redux';
import { store as defaultStore } from '@/store/store';

type AppStore = typeof defaultStore;

export function renderWithProviders(
    ui: React.ReactElement,
    {
        store = defaultStore,
        ...renderOptions
    }: RenderOptions & {
        store?: AppStore;
    } = {},
) {
    function Wrapper({ children }: PropsWithChildren) {
        return <Provider store={store}>{children}</Provider>;
    }

    return {
        store,
        ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    };
}
