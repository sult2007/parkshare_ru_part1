'use client';
import { useState } from 'react';
import { ChatPanel } from '@/components/chat/chat-panel';
import { XMarkIcon } from '@heroicons/react/24/outline';

export function ChatWidget() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 rounded-full bg-gradient-to-r from-indigo-500 to-blue-500 px-5 py-3 text-sm font-semibold text-white shadow-xl transition hover:-translate-y-[1px] hover:shadow-2xl"
        >
          AI Assistant
        </button>
      )}

      {open && (
        <div className="fixed bottom-6 right-6 z-50 bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-[420px] max-h-[80vh] flex flex-col border border-slate-200 dark:border-slate-700">
          <div className="flex justify-between items-center p-3 border-b dark:border-slate-700">
            <h3 className="font-semibold text-slate-800 dark:text-slate-200">AI Assistant</h3>
            <button
              onClick={() => setOpen(false)}
              className="rounded-full border border-slate-200 bg-white p-1 text-slate-600 shadow-sm transition hover:-translate-y-[1px] hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              aria-label="Закрыть виджет"
            >
              <XMarkIcon className="h-4 w-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            <ChatPanel />
          </div>
        </div>
      )}
    </>
  );
}
