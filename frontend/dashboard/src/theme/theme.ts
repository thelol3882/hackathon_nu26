import {createTheme, type CSSVariablesResolver, type MantineColorsTuple} from '@mantine/core';

const ktzBlue: MantineColorsTuple = [
    '#e5f4ff',
    '#b8dfff',
    '#8acaff',
    '#5cb5ff',
    '#2e9fff',
    '#0388e6',
    '#0377b4',
    '#025d8c',
    '#014364',
    '#00293d',
];

const ktzNavy: MantineColorsTuple = [
    '#e8f0f7',
    '#c2d6e8',
    '#9bbcd9',
    '#74a2ca',
    '#4d88bb',
    '#2a6e9e',
    '#095173',
    '#073d58',
    '#052a3d',
    '#0a1628',
];

const ktzCyan: MantineColorsTuple = [
    '#e0fbff',
    '#b3f2ff',
    '#80e8ff',
    '#4ddfff',
    '#1ad5ff',
    '#00b0cb',
    '#008da3',
    '#006a7a',
    '#004752',
    '#002429',
];

const ktzGold: MantineColorsTuple = [
    '#fffbe5',
    '#fff3b8',
    '#ffeb8a',
    '#ffe35c',
    '#ffdb2e',
    '#fec604',
    '#cb9e03',
    '#987702',
    '#654f01',
    '#332800',
];

const healthy: MantineColorsTuple = [
    '#f0fdf4',
    '#dcfce7',
    '#bbf7d0',
    '#86efac',
    '#4ade80',
    '#22c55e',
    '#16a34a',
    '#15803d',
    '#166534',
    '#14532d',
];

const warning: MantineColorsTuple = [
    '#fffbeb',
    '#fef3c7',
    '#fde68a',
    '#fcd34d',
    '#fbbf24',
    '#f59e0b',
    '#d97706',
    '#b45309',
    '#92400e',
    '#78350f',
];

const critical: MantineColorsTuple = [
    '#fef2f2',
    '#fee2e2',
    '#fecaca',
    '#fca5a5',
    '#f87171',
    '#ef4444',
    '#dc2626',
    '#b91c1c',
    '#991b1b',
    '#7f1d1d',
];

export const theme = createTheme({
    primaryColor: 'ktzBlue',
    primaryShade: {light: 6, dark: 4},
    defaultRadius: 'md',

    colors: {
        ktzBlue,
        ktzNavy,
        ktzCyan,
        ktzGold,
        healthy,
        warning,
        critical,
    },

    fontFamily: 'var(--font-body), system-ui, sans-serif',
    headings: {
        fontFamily: 'var(--font-mono), monospace',
    },

    components: {
        Card: {
            defaultProps: {
                withBorder: true,
                padding: 'md',
            },
            styles: {
                root: {
                    backgroundColor: 'var(--dashboard-surface)',
                    borderColor: 'var(--dashboard-border)',
                    borderRadius: 'var(--dashboard-panel-radius)',
                },
            },
        },
        Paper: {
            styles: {
                root: {
                    backgroundColor: 'var(--dashboard-surface)',
                    borderColor: 'var(--dashboard-border)',
                },
            },
        },
        Button: {
            defaultProps: {
                radius: 'md',
            },
        },
        Badge: {
            defaultProps: {
                radius: 'sm',
                variant: 'light',
            },
        },
        Modal: {
            defaultProps: {
                centered: true,
                overlayProps: {blur: 4},
            },
        },
        Select: {
            defaultProps: {radius: 'md', size: 'sm'},
        },
        TextInput: {
            defaultProps: {radius: 'md', size: 'sm'},
        },
        NumberInput: {
            defaultProps: {radius: 'md', size: 'sm'},
        },
        PasswordInput: {
            defaultProps: {radius: 'md', size: 'sm'},
        },
        Tooltip: {
            defaultProps: {
                withArrow: true,
                transitionProps: {transition: 'fade', duration: 200},
            },
        },
    },
});

export const cssVariablesResolver: CSSVariablesResolver = (mantineTheme) => ({
    variables: {
        '--dashboard-gauge-size': '240px',
        '--dashboard-panel-radius': mantineTheme.radius.md,
        '--dashboard-sidebar-width': '260px',
        '--dashboard-sidebar-collapsed': '72px',
        '--dashboard-topbar-height': '60px',
    },
    light: {
        '--dashboard-bg': '#f1f3f5',
        '--dashboard-surface': '#ffffff',
        '--dashboard-surface-elevated': '#f8f9fa',
        '--dashboard-border': '#dee2e6',
        '--dashboard-text-primary': '#1a1b1e',
        '--dashboard-text-secondary': '#495057',
        '--dashboard-glow-healthy': 'rgba(34,197,94,0.15)',
        '--dashboard-glow-warning': 'rgba(254,198,4,0.15)',
        '--dashboard-glow-critical': 'rgba(239,68,68,0.15)',
    },
    dark: {
        '--dashboard-bg': '#0a1628',
        '--dashboard-surface': '#0f2035',
        '--dashboard-surface-elevated': '#132a45',
        '--dashboard-border': '#1a3a5c',
        '--dashboard-text-primary': '#e1e7ef',
        '--dashboard-text-secondary': '#8899aa',
        '--dashboard-glow-healthy': 'rgba(34,197,94,0.25)',
        '--dashboard-glow-warning': 'rgba(254,198,4,0.25)',
        '--dashboard-glow-critical': 'rgba(239,68,68,0.3)',
    },
});
