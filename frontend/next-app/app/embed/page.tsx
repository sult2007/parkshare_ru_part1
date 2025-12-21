import { CompactChatPanel } from '@/components/chat/compact-chat-panel';
import { chatEnabled } from '@/lib/featureFlags';

export const metadata = {
  title: 'AI Concierge – Embed'
};

export default function EmbedPage() {
  if (!chatEnabled) {
    return (
      <main className="min-h-screen bg-slate-950 flex items-center justify-center p-2">
        <div className="w-full max-w-md rounded-3xl bg-slate-900/90 shadow-2xl border border-slate-700/80 overflow-hidden p-6 text-center text-slate-100">
          <p className="text-sm font-semibold">AI чат отключён</p>
          <p className="mt-2 text-xs text-slate-300">Встраиваемый виджет временно недоступен.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 flex items-center justify-center p-2">
      <div className="w-full max-w-md h-[80vh] rounded-3xl bg-slate-900/90 shadow-2xl border border-slate-700/80 overflow-hidden">
        <CompactChatPanel />
      </div>
    </main>
  );
}
