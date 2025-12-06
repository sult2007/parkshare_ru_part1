import './globals.css';
import { Providers } from '@/components/providers';
import { Header } from '@/components/header';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth';
import type { Metadata } from 'next';
import { ServiceWorkerRegistrar } from '@/components/pwa/register-service-worker';

export const metadata: Metadata = {
  title: 'ParkShare AI Concierge',
  description: 'AI-powered chat assistant for ParkShare partners',
  manifest: '/manifest.webmanifest',
  themeColor: '#0f172a'
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await getServerSession(authOptions);

  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers session={session}>
          <div className="flex min-h-screen flex-col bg-surface dark:bg-surface-dark">
            <Header />
            <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 p-4">{children}</main>
            <ServiceWorkerRegistrar />
          </div>
        </Providers>
      </body>
    </html>
  );
}
