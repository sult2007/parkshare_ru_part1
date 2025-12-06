'use client';

import { useMemo } from 'react';
import { Conversation } from './types';
import { PlusIcon, PencilSquareIcon, TrashIcon } from '@heroicons/react/24/outline';

interface ConversationListProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onRename: (id: string, name: string) => void;
  onDelete: (id: string) => void;
  onClose?: () => void;
}

function formatTimestamp(timestamp: number) {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / (1000 * 60));
  if (minutes < 60) return `${minutes || 1}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function ConversationList({ conversations, activeId, onSelect, onCreate, onRename, onDelete, onClose }: ConversationListProps) {
  const sorted = useMemo(() => [...conversations].sort((a, b) => b.updatedAt - a.updatedAt), [conversations]);

  return (
    <aside className="flex h-full flex-col rounded-3xl border border-slate-200/80 bg-white/70 p-4 shadow-md backdrop-blur dark:border-slate-800/60 dark:bg-slate-900/70">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">Conversations</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Jump back into previous threads</p>
        </div>
        <button
          onClick={onCreate}
          className="flex items-center gap-1 rounded-full bg-gradient-to-r from-indigo-500 to-blue-500 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:shadow-md"
        >
          <PlusIcon className="h-4 w-4" />
          New
        </button>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto pr-1">
        {sorted.map((conversation) => {
          const isActive = conversation.id === activeId;
          const lastMessage = conversation.messages[conversation.messages.length - 1];
          return (
            <div
              key={conversation.id}
              className={`group relative overflow-hidden rounded-2xl border border-transparent transition hover:border-indigo-200 hover:bg-indigo-50/50 dark:hover:border-indigo-600/40 dark:hover:bg-indigo-950/30 ${
                isActive
                  ? 'border-indigo-300 bg-indigo-50 dark:border-indigo-600/60 dark:bg-indigo-900/40'
                  : 'border-slate-100 dark:border-slate-800'
              }`}
            >
              <button
                onClick={() => {
                  onSelect(conversation.id);
                  onClose?.();
                }}
                className="flex w-full flex-col gap-1 px-3 py-3 text-left"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="line-clamp-1 text-sm font-semibold text-slate-800 dark:text-slate-50">{conversation.title}</p>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400">{formatTimestamp(conversation.updatedAt)}</span>
                </div>
                <p className="line-clamp-2 text-xs text-slate-500 dark:text-slate-400">
                  {lastMessage?.content || 'Empty conversation'}
                </p>
              </button>
              <div className="absolute right-2 top-2 flex gap-1 opacity-0 transition group-hover:opacity-100">
                <button
                  aria-label="Rename conversation"
                  onClick={() => {
                    const nextName = prompt('Rename conversation', conversation.title);
                    if (nextName?.trim()) {
                      onRename(conversation.id, nextName.trim());
                    }
                  }}
                  className="rounded-full bg-white/90 p-1 text-slate-500 shadow hover:text-indigo-600 dark:bg-slate-800/80"
                >
                  <PencilSquareIcon className="h-4 w-4" />
                </button>
                <button
                  aria-label="Delete conversation"
                  onClick={() => {
                    const confirmed = confirm('Delete this conversation? This cannot be undone.');
                    if (confirmed) {
                      onDelete(conversation.id);
                    }
                  }}
                  className="rounded-full bg-white/90 p-1 text-slate-500 shadow hover:text-red-600 dark:bg-slate-800/80"
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
              </div>
            </div>
          );
        })}
        {sorted.length === 0 && (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 p-4 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800/40 dark:text-slate-400">
            No conversations yet.
          </div>
        )}
      </div>
    </aside>
  );
}
