import '@mantine/core/styles.css';
import '@mantine/dates/styles.css';
import '@mantine/charts/styles.css';
import '@mantine/notifications/styles.css';
import '@mantine/tiptap/styles.css';
import '@mantine/dropzone/styles.css';
import '@mantine/carousel/styles.css';
import '@mantine/spotlight/styles.css';
import '@mantine/nprogress/styles.css';
import './globals.css';

import { ColorSchemeScript, mantineHtmlProps } from '@mantine/core';
import { Share_Tech_Mono, Nunito_Sans } from 'next/font/google';
import type { Metadata } from 'next';
import { Providers } from '@/providers';

export const metadata: Metadata = {
    title: 'КТЖ — Цифровой двойник локомотива',
    description:
        'Система мониторинга телеметрии локомотивов в реальном времени. Индекс здоровья, оповещения, тренды, отчёты.',
    icons: { icon: '/favicon.ico' },
};

const shareTechMono = Share_Tech_Mono({
    weight: '400',
    subsets: ['latin'],
    variable: '--font-mono',
    display: 'swap',
});

const nunitoSans = Nunito_Sans({
    subsets: ['latin', 'cyrillic'],
    variable: '--font-body',
    display: 'swap',
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html
            lang="ru"
            className={`${shareTechMono.variable} ${nunitoSans.variable}`}
            {...mantineHtmlProps}
        >
            <head>
                <ColorSchemeScript defaultColorScheme="dark" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
            </head>
            <body>
                <Providers>{children}</Providers>
            </body>
        </html>
    );
}
