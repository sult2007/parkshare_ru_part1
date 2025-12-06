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
    <section className="flex flex-1 flex-col gap-6">
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-r from-blue-50 via-white to-indigo-50 p-6 shadow-md dark:border-slate-800 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950/50">
        <div className="flex flex-col gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-500">AI Concierge</p>
          <h1 className="text-3xl font-semibold text-slate-900 dark:text-slate-50">Conversational partner for ParkShare teams</h1>
          <p className="max-w-3xl text-sm text-slate-600 dark:text-slate-400">
            Deepen your operational insight with guided prompts, persistent threads, and rich responses. Tap a preset to move faster or
            start a fresh conversation for a new idea.
          </p>
        </div>
      </div>
      <ChatPanel />
    </section>
  );
}
