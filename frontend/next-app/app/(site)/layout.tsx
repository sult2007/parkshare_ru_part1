import { Providers } from '@/components/providers';
import { Header } from '@/components/header';
import { ServiceWorkerRegistrar } from '@/components/pwa/register-service-worker';
import { ChatWidget } from '@/components/widget/chat-widget';

export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <div className="flex min-h-screen flex-col bg-surface dark:bg-surface-dark">
        <Header />
        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 p-4">{children}</main>
        <ServiceWorkerRegistrar />
        <ChatWidget />
      </div>
    </Providers>
  );
}
