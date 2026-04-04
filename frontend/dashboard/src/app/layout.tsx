import '@mantine/core/styles.css';
import '@mantine/core/styles.css';
import '@mantine/dates/styles.css';
import '@mantine/charts/styles.css';
import '@mantine/notifications/styles.css';
import '@mantine/tiptap/styles.css';
import '@mantine/dropzone/styles.css';
import '@mantine/carousel/styles.css';
import '@mantine/spotlight/styles.css';
import '@mantine/nprogress/styles.css';


import { ColorSchemeScript, MantineProvider, mantineHtmlProps } from '@mantine/core';

export default function RootLayout({
                                     children,
                                   }: {
  children: React.ReactNode;
}) {
  return (
      <html lang="ru" {...mantineHtmlProps}>
      <head>
        <ColorSchemeScript />
      </head>
      <body>
      <MantineProvider>{children}</MantineProvider>
      </body>
      </html>
  );
}