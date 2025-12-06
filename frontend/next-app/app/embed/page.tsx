import { ChatPanel } from '@/components/chat/chat-panel';

export default function EmbedPage() {
  return (
    <main className="min-h-screen bg-slate-100 dark:bg-slate-950 flex justify-center items-start p-4">
      <div className="w-full max-w-4xl">
        <ChatPanel />
      </div>
    </main>
  );
}
