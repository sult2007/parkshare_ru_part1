'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type React from 'react';
import dynamic from 'next/dynamic';
import { PaperAirplaneIcon, SparklesIcon, ClockIcon, ArrowPathIcon, Bars3Icon } from '@heroicons/react/24/outline';
import { ChatMessage } from '@/lib/aiProvider';
import { Conversation, MessageWithId } from './types';
import { ConversationList } from './conversation-list';
import { SuggestedPrompts } from './suggested-prompts';

const MarkdownMessage = dynamic(() => import('./markdown-message'), {
  ssr: false,
  loading: () => <div className="h-4 w-24 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700" />
});

const STORAGE_KEY = 'parkshare_conversations_v1';
const MAX_HISTORY = 14;

const createWelcomeMessage = (): MessageWithId => ({
  id: crypto.randomUUID(),
  role: 'assistant',
  content: 'Hi! I am your ParkShare AI concierge. Ask me about occupancy, pricing, or customer journeys.',
  createdAt: Date.now()
});

const createConversation = (title = 'New conversation'): Conversation => ({
  id: crypto.randomUUID(),
  title,
  messages: [createWelcomeMessage()],
  updatedAt: Date.now()
});

export function ChatPanel() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const hasBootstrapped = useRef(false);

  useEffect(() => {
    if (typeof window === 'undefined' || hasBootstrapped.current) return;
    hasBootstrapped.current = true;
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed: Conversation[] = JSON.parse(stored);
        setConversations(parsed);
        setActiveConversationId(parsed[0]?.id ?? null);
        return;
      }
    } catch (error) {
      console.warn('Failed to parse saved conversations', error);
    }
    const starter = createConversation('Welcome thread');
    setConversations([starter]);
    setActiveConversationId(starter.id);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [conversations, activeConversationId]);

  const currentConversation = useMemo(
    () => conversations.find((conv) => conv.id === activeConversationId) ?? null,
    [conversations, activeConversationId]
  );

  const updateConversation = useCallback(
    (id: string, updater: (conversation: Conversation) => Conversation) => {
      setConversations((prev) => prev.map((conv) => (conv.id === id ? updater(conv) : conv)));
    },
    []
  );

  const handleCreate = useCallback(() => {
    const conversation = createConversation('New idea');
    setConversations((prev) => [conversation, ...prev]);
    setActiveConversationId(conversation.id);
  }, []);

  const handleRename = useCallback((id: string, name: string) => {
    updateConversation(id, (conv) => ({ ...conv, title: name, updatedAt: Date.now() }));
  }, [updateConversation]);

  const handleDelete = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const remaining = prev.filter((conv) => conv.id !== id);
        if (id === activeConversationId) {
          setActiveConversationId(remaining[0]?.id ?? null);
        }
        return remaining;
      });
    },
    [activeConversationId]
  );

  const handleSend = useCallback(async () => {
    if (!currentConversation || !input.trim() || isLoading) return;

    const userMessage: MessageWithId = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      createdAt: Date.now()
    };

    setInput('');
    setIsLoading(true);

    updateConversation(currentConversation.id, (conv) => {
      const trimmedHistory = [...conv.messages, userMessage].slice(-MAX_HISTORY);
      return { ...conv, messages: trimmedHistory, updatedAt: Date.now() };
    });

    const assistantMessage: MessageWithId = { id: crypto.randomUUID(), role: 'assistant', content: '', createdAt: Date.now() };
    updateConversation(currentConversation.id, (conv) => ({
      ...conv,
      messages: [...conv.messages, assistantMessage].slice(-MAX_HISTORY),
      updatedAt: Date.now()
    }));

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          messages: currentConversation.messages
            .concat(userMessage)
            .slice(-MAX_HISTORY)
            .map(({ id, createdAt, ...rest }) => rest as ChatMessage)
        })
      });

      if (!response.ok || !response.body) {
        throw new Error('Failed to reach chat API');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const textChunk = decoder.decode(value, { stream: true });
        updateConversation(currentConversation.id, (conv) => ({
          ...conv,
          messages: conv.messages.map((msg) =>
            msg.id === assistantMessage.id ? { ...msg, content: msg.content + textChunk } : msg
          ),
          updatedAt: Date.now()
        }));
      }
    } catch (error) {
      console.error(error);
      updateConversation(currentConversation.id, (conv) => ({
        ...conv,
        messages: conv.messages.map((msg) =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                content: 'Something went wrong reaching the AI. Please confirm your API key and try again.'
              }
            : msg
        ),
        updatedAt: Date.now()
      }));
    } finally {
      setIsLoading(false);
    }
  }, [currentConversation, input, isLoading, updateConversation]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  const handlePrefill = useCallback((prompt: string) => {
    setInput(prompt);
  }, []);

  const sendDisabled = isLoading || !input.trim();

  return (
    <div className="relative flex min-h-[70vh] flex-1 flex-col overflow-hidden rounded-3xl border border-slate-200/80 bg-gradient-to-br from-slate-50 via-white to-indigo-50 p-4 shadow-lg dark:border-slate-800/80 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950/40">
      <div className="mb-4 flex flex-col gap-3 rounded-3xl border border-slate-200/60 bg-white/70 p-4 backdrop-blur dark:border-slate-800/70 dark:bg-slate-900/60">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-md">
              <SparklesIcon className="h-6 w-6" />
            </div>
            <div>
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-50">AI Concierge</p>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Smarter conversations with memory, suggestions, and offline-ready polish.
              </p>
            </div>
          </div>
          <button
            className="flex items-center gap-2 rounded-full border border-slate-200 bg-white/60 px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-800 dark:bg-slate-800/80 dark:text-slate-200 dark:hover:border-indigo-500/60"
            onClick={handleCreate}
          >
            <ArrowPathIcon className="h-4 w-4" />
            Reset thread
          </button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <ClockIcon className="h-4 w-4" />
            <span>Sessions persist locally. Rename, delete, or pick up where you left off.</span>
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-full border border-indigo-200/80 bg-indigo-50 px-3 py-2 text-xs font-semibold text-indigo-700 shadow-sm transition hover:-translate-y-[1px] hover:shadow-md dark:border-indigo-500/50 dark:bg-indigo-900/40 dark:text-indigo-100"
            onClick={() => setShowSidebar(true)}
          >
            <Bars3Icon className="h-4 w-4" />
            Conversations
          </button>
        </div>
        <SuggestedPrompts onSelect={handlePrefill} />
      </div>

      <div className="grid h-full grid-cols-1 gap-4 lg:grid-cols-[320px,1fr]">
        <div className="hidden lg:block">
          <ConversationList
            conversations={conversations}
            activeId={activeConversationId}
            onSelect={(id) => setActiveConversationId(id)}
            onCreate={handleCreate}
            onRename={handleRename}
            onDelete={handleDelete}
          />
        </div>
        <div className="flex flex-col overflow-hidden rounded-3xl border border-slate-200/80 bg-white/80 shadow-md backdrop-blur dark:border-slate-800/70 dark:bg-slate-900/70">
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6">
            {currentConversation?.messages.map((message) => (
              <MessageBubble key={message.id} message={message} isLoading={isLoading} />
            ))}
            <div ref={chatEndRef} />
          </div>
          <div className="border-t border-slate-200 bg-gradient-to-r from-slate-50/90 via-white to-slate-50/90 p-4 dark:border-slate-800 dark:from-slate-900/80 dark:via-slate-900 dark:to-slate-900/80">
            <div className="flex flex-col gap-2">
              <label htmlFor="chat-input" className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Ask the concierge
              </label>
              <div className="flex flex-col gap-3 rounded-2xl border border-slate-200/70 bg-white/70 p-3 shadow-sm transition focus-within:border-indigo-200 focus-within:ring-1 focus-within:ring-indigo-200 dark:border-slate-800/60 dark:bg-slate-900/70 dark:focus-within:border-indigo-500/50 dark:focus-within:ring-indigo-500/50">
                <textarea
                  id="chat-input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={3}
                  className="flex-1 resize-none border-none bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-slate-100"
                  placeholder="How can I optimize pricing for weekend events?"
                />
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Enter to send • Shift + Enter for new line</p>
                  <button
                    onClick={() => void handleSend()}
                    disabled={sendDisabled}
                    className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-500 to-blue-500 px-4 py-2 text-sm font-semibold text-white shadow-md transition hover:-translate-y-[1px] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <PaperAirplaneIcon className="h-5 w-5" />
                    Send
                  </button>
                </div>
              </div>
              {isLoading && <p className="text-xs text-slate-500">Streaming response…</p>}
            </div>
          </div>
        </div>
      </div>

      {showSidebar && (
        <div className="fixed inset-0 z-30 flex bg-black/50 backdrop-blur-sm lg:hidden">
          <div className="m-4 flex w-full max-w-sm flex-col">
            <ConversationList
              conversations={conversations}
              activeId={activeConversationId}
              onSelect={(id) => setActiveConversationId(id)}
              onCreate={() => {
                handleCreate();
                setShowSidebar(false);
              }}
              onRename={handleRename}
              onDelete={handleDelete}
              onClose={() => setShowSidebar(false)}
            />
            <button
              onClick={() => setShowSidebar(false)}
              className="mt-3 rounded-2xl border border-slate-200 bg-white/90 px-3 py-2 text-sm text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const MessageBubble = React.memo(function MessageBubble({
  message,
  isLoading
}: {
  message: MessageWithId;
  isLoading: boolean;
}) {
  const isUser = message.role === 'user';
  const timestamp = useMemo(() => new Date(message.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), [message.createdAt]);
  const bubbleClass = useMemo(
    () =>
      `group relative max-w-3xl rounded-2xl px-4 py-3 text-sm shadow-sm transition-all duration-200 ${
        isUser
          ? 'ml-auto bg-gradient-to-r from-indigo-500 to-blue-500 text-white'
          : 'bg-slate-100/90 text-slate-900 dark:bg-slate-800/80 dark:text-slate-50'
      }`,
    [isUser]
  );

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={bubbleClass}>
        <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          <span className="inline-flex items-center rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700 dark:bg-slate-700 dark:text-slate-200">
            {isUser ? 'You' : 'AI'}
          </span>
          <span className="text-[10px] text-slate-500 dark:text-slate-400">{timestamp}</span>
        </div>
        {isUser ? (
          <p className="whitespace-pre-line leading-relaxed">{message.content}</p>
        ) : message.content ? (
          <div className="transition-opacity duration-200">
            <MarkdownMessage content={message.content} />
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="h-3 w-24 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700" />
            <div className="h-3 w-36 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700" />
            {isLoading && <div className="h-3 w-16 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700" />}
          </div>
        )}
      </div>
    </div>
  );
});
