import {
    IconGauge,
    IconFileAnalytics,
    IconSettings,
} from '@tabler/icons-react';
import type { ComponentType } from 'react';

export interface NavItem {
    key: string;
    href: string;
    icon: ComponentType<{ size?: number | string; stroke?: number }>;
    label: string;
    adminOnly?: boolean;
}

export const navigationItems: NavItem[] = [
    { key: 'dashboard', href: '/dashboard', icon: IconGauge, label: 'Кабина' },
    { key: 'reports', href: '/reports', icon: IconFileAnalytics, label: 'Отчёты' },
    { key: 'config', href: '/config', icon: IconSettings, label: 'Настройки', adminOnly: true },
];
