'use client';
import { useState } from 'react';
import { ChatPanel } from '@/components/chat/chat-panel';

export function ChatWidget() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-3 rounded-full shadow-xl text-sm font-semibold"
        >
          AI Assistant
        </button>
      )}

      {open && (
        <div className="fixed bottom-6 right-6 z-50 bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-[420px] max-h-[80vh] flex flex-col border border-slate-200 dark:border-slate-700">
          <div className="flex justify-between items-center p-3 border-b dark:border-slate-700">
            <h3 className="font-semibold text-slate-800 dark:text-slate-200">AI Assistant</h3>
            <button onClick={() => setOpen(false)}>✕</button>
          </div>
          <div className="flex-1 overflow-y-auto">
            <ChatPanel />
          </div>
        </div>
      )}
    </>
  );
}
