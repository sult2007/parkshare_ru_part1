import { redirect } from 'next/navigation';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth';
import { ChatPanel } from '@/components/chat/chat-panel';

export default async function HomePage() {
  const session = await getServerSession(authOptions);
  if (!session) {
    redirect('/login');
  }

  return (
    <section className="flex flex-1 flex-col gap-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h1 className="text-2xl font-semibold">AI Chat Assistant</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Ask anything about your parking operations, pricing, or customer experience. Responses stream live from the AI model.
        </p>
      </div>
      <ChatPanel />
    </section>
  );
}
