import './globals.css';
import type { ReactNode } from 'react';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <meta name="theme-color" content="#0f172a" />
      </head>
      <body className="bg-[var(--bg-surface)] text-[var(--text-primary)]">{children}</body>
    </html>
  );
}
