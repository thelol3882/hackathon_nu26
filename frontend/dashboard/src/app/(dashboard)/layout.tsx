'use client';

import {useAppSelector} from '@/store/hooks';
import {selectIsAuthenticated} from '@/store/authSlice';
import {useRouter} from 'next/navigation';
import {useEffect} from 'react';
import {DashboardLayout} from '@/widgets/layout';

export default function DashboardGroupLayout({children}: { children: React.ReactNode }) {
    const isAuthenticated = useAppSelector(selectIsAuthenticated);
    const router = useRouter();

    useEffect(() => {
        if (!isAuthenticated) {
            router.replace('/login');
        }
    }, [isAuthenticated, router]);

    if (!isAuthenticated) return null;

    return <DashboardLayout>{children}</DashboardLayout>;
}
