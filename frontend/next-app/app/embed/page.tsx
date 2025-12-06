import { CompactChatPanel } from '@/components/chat/compact-chat-panel';

export const metadata = {
  title: 'AI Concierge – Embed'
};

export default function EmbedPage() {
  return (
    <main className="min-h-screen bg-slate-950 flex items-center justify-center p-2">
      <div className="w-full max-w-md h-[80vh] rounded-3xl bg-slate-900/90 shadow-2xl border border-slate-700/80 overflow-hidden">
        <CompactChatPanel />
      </div>
    </main>
  );
}