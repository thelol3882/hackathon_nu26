import {
    IconGauge,
    IconFileAnalytics,
    IconSettings,
    IconUsers,
    IconMapPins,
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
    { key: 'fleet', href: '/fleet', icon: IconMapPins, label: 'Локомотивы' },
    { key: 'reports', href: '/reports', icon: IconFileAnalytics, label: 'Отчёты' },
    { key: 'users', href: '/users', icon: IconUsers, label: 'Пользователи', adminOnly: true },
    { key: 'config', href: '/config', icon: IconSettings, label: 'Настройки', adminOnly: true },
];
