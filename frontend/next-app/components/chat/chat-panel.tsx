'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  PaperAirplaneIcon,
  SparklesIcon,
  ClockIcon,
  ArrowPathIcon,
  Bars3Icon,
  ClipboardIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';
import { ChatMessage } from '@/lib/aiProvider';
import { chatEnabled } from '@/lib/featureFlags';
import { Conversation, MessageWithId } from './types';
import { ConversationList } from './conversation-list';
import { SuggestedPrompts } from './suggested-prompts';
import { apiRequest, type AssistantAction, type AssistantResponse, type BookingSession } from '@/lib/apiClient';
import { useAuth } from '@/hooks/useAuth';

const MarkdownMessage = dynamic(() => import('./markdown-message'), {
  ssr: false,
  loading: () => <div className="h-4 w-24 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700" />
});

const STORAGE_KEY_BASE = 'parkshare_conversations_v2';
const ONBOARDING_KEY = 'parkshare_onboarding_seen';
const MAX_HISTORY = 14;
const FAVORITE_PROMPTS = [
  'Сформируй чат-скрипт для диспетчера парковки с VIP-клиентами.',
  'Собери сводку по пиковым часам и дай рекомендации по динамическим тарифам.',
  'Сценарий поддержки: клиент не может найти въезд. Какие шаги предложить?',
  'Что добавить в онбординг партнёра, чтобы повысить NPS?',
  'Сделай контрольный чек-лист для запуска новой парковки на выходные.'
];

const createWelcomeMessage = (): MessageWithId => ({
  id: crypto.randomUUID(),
  role: 'assistant',
  content: 'Привет! Я ParkShare AI Concierge. Спроси про загрузку, цены, сценарии для гостей или подготовку персонала.',
  createdAt: Date.now()
});

const createConversation = (title = 'New conversation'): Conversation => ({
  id: crypto.randomUUID(),
  title,
  messages: [createWelcomeMessage()],
  updatedAt: Date.now()
});

const storageKeyForUser = (userId?: string | null) => `${STORAGE_KEY_BASE}:${userId ?? 'guest'}`;

export function ChatPanel() {
  if (!chatEnabled) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center rounded-3xl border border-[var(--border-subtle)]/70 bg-[var(--bg-elevated)] p-6 text-sm text-[var(--text-muted)] shadow-sm">
        AI чат отключён.
      </div>
    );
  }

  const { user, isAuthenticated } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [sessions, setSessions] = useState<BookingSession[]>([]);
  const [alerts, setAlerts] = useState<{ booking_id?: string; type: string; minutes_left?: number; spot?: string }[]>([]);
  const [actions, setActions] = useState<AssistantAction[]>([]);
  const [sessionsFetchedAt, setSessionsFetchedAt] = useState<number | null>(null);
  const [actionRunning, setActionRunning] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const lastStorageKey = useRef<string | null>(null);

  const storageKey = useMemo(() => storageKeyForUser(user?.id), [user?.id]);

  useEffect(() => {
    if (typeof window === 'undefined' || lastStorageKey.current === storageKey) return;
    lastStorageKey.current = storageKey;
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed: Conversation[] = JSON.parse(stored);
        setConversations(parsed);
        setActiveConversationId(parsed[0]?.id ?? null);
        return;
      }
    } catch (error) {
      console.warn('Failed to parse saved conversations', error);
    }
    // TODO: Mirror conversation history to a backend store for multi-device sync and tenant scoping.
    const starter = createConversation('Welcome thread');
    setConversations([starter]);
    setActiveConversationId(starter.id);
  }, [storageKey]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(storageKey, JSON.stringify(conversations));
  }, [conversations, storageKey]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const seen = localStorage.getItem(ONBOARDING_KEY);
    if (!seen) {
      setShowOnboarding(true);
      localStorage.setItem(ONBOARDING_KEY, 'true');
    }
  }, []);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    void fetchSessions();
  }, [fetchSessions]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [conversations, activeConversationId]);

  const currentConversation = useMemo(
    () => conversations.find((conv) => conv.id === activeConversationId) ?? null,
    [conversations, activeConversationId]
  );

  const bookingActions = useMemo(
    () => actions.filter((a) => a.type === 'booking_start' || a.type === 'booking_extend' || a.type === 'booking_stop'),
    [actions]
  );

  const actionLabel = useCallback((action: AssistantAction) => {
    if (action.type === 'booking_start') return 'Начать парковку';
    if (action.type === 'booking_extend') return 'Продлить сессию';
    if (action.type === 'booking_stop') return 'Завершить сессию';
    return 'Действие';
  }, []);

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

  const fetchSessions = useCallback(async () => {
    if (!isAuthenticated) {
      setSessions([]);
      setSessionsFetchedAt(Date.now());
      return;
    }
    try {
      const response = await apiRequest<{ results: BookingSession[] }>('/booking/active/', { method: 'GET' });
      setSessions(response.results || []);
      setSessionsFetchedAt(Date.now());
    } catch (error) {
      console.warn('Failed to load active sessions', error);
    }
  }, [isAuthenticated]);

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

  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversationId(id);
    setShowSidebar(false);
  }, []);

  const deliverAssistantReply = useCallback(
    (conversationId: string, assistantMessageId: string, reply: string) => {
      updateConversation(conversationId, (conv) => ({
        ...conv,
        messages: conv.messages.map((msg) => (msg.id === assistantMessageId ? { ...msg, content: reply } : msg)),
        updatedAt: Date.now()
      }));
    },
    [updateConversation]
  );

  const requestAssistant = useCallback(
    async (conversationId: string, assistantMessageId: string, history: ChatMessage[]) => {
      const response = await apiRequest<AssistantResponse>('/assistant/chat/', {
        method: 'POST',
        body: { messages: history, structured: true }
      });
      deliverAssistantReply(conversationId, assistantMessageId, response.reply || 'Сервис временно недоступен.');
      setActions(response.actions || []);
      setAlerts(response.alerts || []);
      if (response.sessions) {
        setSessions(response.sessions);
        setSessionsFetchedAt(Date.now());
      }
      return response;
    },
    [deliverAssistantReply]
  );

  const handleAction = useCallback(
    async (action: AssistantAction) => {
      const actionKey = action.booking_id || action.spot_id || action.type;
      setActionRunning(actionKey || null);
      try {
        if (action.type === 'booking_start' && action.spot_id) {
          await apiRequest('/booking/start/', {
            method: 'POST',
            body: { spot_id: action.spot_id, duration_minutes: action.duration_minutes || 60 }
          });
        } else if (action.type === 'booking_extend' && action.booking_id) {
          await apiRequest('/booking/extend/', {
            method: 'POST',
            body: { booking_id: action.booking_id, extend_minutes: action.extend_minutes || 30 }
          });
        } else if (action.type === 'booking_stop' && action.booking_id) {
          await apiRequest('/booking/stop/', { method: 'POST', body: { booking_id: action.booking_id } });
        } else if (action.type === 'focus_map' && action.spot_id) {
          try {
            sessionStorage.setItem('ps_focus_spot', action.spot_id);
          } catch (err) {
            console.warn('Cannot persist focus spot', err);
          }
          window.location.href = '/';
        } else if (action.type === 'book' && action.spot_id) {
          window.location.href = `/booking/confirm/?spot_id=${encodeURIComponent(action.spot_id)}`;
        }
        await fetchSessions();
      } catch (err) {
        console.error('Action failed', err);
        setErrorMessage(err instanceof Error ? err.message : 'Не удалось выполнить действие ассистента.');
      } finally {
        setActionRunning(null);
      }
    },
    [fetchSessions]
  );

  const computeRemaining = useCallback(
    (session: BookingSession) => {
      const elapsed = sessionsFetchedAt ? Math.floor((Date.now() - sessionsFetchedAt) / 1000) : 0;
      return Math.max(0, session.remaining_seconds - elapsed);
    },
    [sessionsFetchedAt]
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
    setErrorMessage(null);

    const historyPayload: ChatMessage[] = currentConversation.messages
      .concat(userMessage)
      .slice(-MAX_HISTORY)
      .map(({ id, createdAt, ...rest }) => rest as ChatMessage);

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
      await requestAssistant(currentConversation.id, assistantMessage.id, historyPayload);
    } catch (error) {
      console.error(error);
      setErrorMessage('Мы не смогли обратиться к ассистенту. Попробуйте снова или проверьте подключение.');
      deliverAssistantReply(
        currentConversation.id,
        assistantMessage.id,
        'Ассистент временно недоступен. Проверьте подключение или авторизацию и повторите.'
      );
    } finally {
      setIsLoading(false);
    }
  }, [currentConversation, input, isLoading, requestAssistant, deliverAssistantReply, updateConversation]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  const handleClear = useCallback(() => {
    if (!currentConversation) return;
    updateConversation(currentConversation.id, (conv) => ({
      ...conv,
      messages: [createWelcomeMessage()],
      updatedAt: Date.now()
    }));
    setInput('');
    setErrorMessage(null);
    setActions([]);
    setAlerts([]);
  }, [currentConversation, updateConversation]);

  const handleRegenerate = useCallback(
    async (assistantMessageId: string) => {
      if (!currentConversation || isLoading) return;
      const targetIndex = currentConversation.messages.findIndex((msg) => msg.id === assistantMessageId);
      if (targetIndex <= 0) return;
      const historyBefore = currentConversation.messages.slice(0, targetIndex);
      const lastUserIndex = [...historyBefore].reverse().findIndex((msg) => msg.role === 'user');
      if (lastUserIndex === -1) return;
      const userIndex = historyBefore.length - 1 - lastUserIndex;
      const historyToSend = currentConversation.messages.slice(0, userIndex + 1);

      setIsLoading(true);
      setErrorMessage(null);

      const assistantMessage: MessageWithId = { id: crypto.randomUUID(), role: 'assistant', content: '', createdAt: Date.now() };
      updateConversation(currentConversation.id, (conv) => ({
        ...conv,
        messages: [...historyToSend, assistantMessage].slice(-MAX_HISTORY),
        updatedAt: Date.now()
      }));

      const payloadMessages: ChatMessage[] = historyToSend.map(({ id, createdAt, ...rest }) => rest as ChatMessage);

      try {
        await requestAssistant(currentConversation.id, assistantMessage.id, payloadMessages);
      } catch (error) {
        console.error(error);
        setErrorMessage('Не удалось перегенерировать ответ. Попробуйте снова.');
        deliverAssistantReply(currentConversation.id, assistantMessage.id, 'Ассистент недоступен. Повторите позже.');
      } finally {
        setIsLoading(false);
      }
    },
    [currentConversation, isLoading, requestAssistant, updateConversation, deliverAssistantReply]
  );

  const handlePrefill = useCallback((prompt: string) => {
    setInput(prompt);
  }, []);

  const sendDisabled = isLoading || !input.trim();

  return (
    <div className="relative flex min-h-[70vh] flex-1 flex-col overflow-hidden rounded-[28px] border border-[var(--border-subtle)]/80 bg-gradient-to-br from-white via-[var(--bg-surface)] to-white p-4 shadow-[0_18px_42px_rgba(15,23,42,0.08)] dark:border-slate-800/80 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950/40">
      <div className="mb-4 flex flex-col gap-4 rounded-3xl border border-slate-200/60 bg-white/70 p-4 backdrop-blur dark:border-slate-800/70 dark:bg-slate-900/60">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-md">
              <SparklesIcon className="h-6 w-6" />
            </div>
            <div className="space-y-0.5">
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-50">AI Concierge</p>
              <p className="text-sm text-slate-600 dark:text-slate-400">Потоковые ответы, готовые пресеты и офлайн-поведение.</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Статус: {isAuthenticated ? 'Личный профиль' : 'Гостевой режим'} • История хранится локально
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              className="flex items-center gap-2 rounded-full border border-slate-200 bg-white/60 px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-800 dark:bg-slate-800/80 dark:text-slate-200 dark:hover:border-indigo-500/60"
              onClick={handleCreate}
            >
              <ArrowPathIcon className="h-4 w-4" />
              Новый диалог
            </button>
            <button
              onClick={handleClear}
              className="flex items-center gap-2 rounded-full border border-slate-200 bg-white/60 px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:border-red-200 hover:text-red-600 dark:border-slate-800 dark:bg-slate-800/80 dark:text-slate-200"
            >
              <StopCircleIcon className="h-4 w-4" />
              Очистить
            </button>
            <button
              className="inline-flex items-center gap-2 rounded-full border border-indigo-200/80 bg-indigo-50 px-3 py-2 text-xs font-semibold text-indigo-700 shadow-sm transition hover:-translate-y-[1px] hover:shadow-md dark:border-indigo-500/50 dark:bg-indigo-900/40 dark:text-indigo-100"
              onClick={() => setShowSidebar(true)}
            >
              <Bars3Icon className="h-4 w-4" />
              Диалоги
            </button>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <ClockIcon className="h-4 w-4" />
            <span>Контекст до 14 сообщений. Профиль влияет на подсказки и историю.</span>
          </div>
          {isLoading && (
            <div className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-[11px] font-semibold text-indigo-700 shadow-sm dark:bg-indigo-900/50 dark:text-indigo-100">
              <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
              Генерируем ответ
            </div>
          )}
        </div>
        <SuggestedPrompts onSelect={handlePrefill} />
        <div className="flex flex-wrap items-center gap-2">
          {FAVORITE_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => handlePrefill(prompt)}
              className="group rounded-full border border-slate-200/70 bg-white/70 px-3 py-2 text-xs text-slate-700 shadow-sm transition hover:-translate-y-[1px] hover:border-slate-300 hover:bg-white dark:border-slate-800 dark:bg-slate-800/80 dark:text-slate-200"
            >
              <span className="mr-2 inline-block h-2 w-2 rounded-full bg-gradient-to-r from-indigo-500 to-blue-500 transition group-hover:scale-110" />
              {prompt}
            </button>
          ))}
        </div>
        {showOnboarding && (
          <div className="rounded-2xl border border-indigo-200 bg-indigo-50/80 px-4 py-3 text-xs text-indigo-800 shadow-sm dark:border-indigo-800/70 dark:bg-indigo-900/40 dark:text-indigo-100">
            <div className="flex items-center justify-between gap-2">
              <p>Подсказки и история сохраняются локально. Нажмите «Диалоги» для быстрого переключения веток.</p>
              <button
                onClick={() => setShowOnboarding(false)}
                className="rounded-full bg-white/70 px-3 py-1 text-[11px] font-semibold text-indigo-700 shadow-sm transition hover:-translate-y-[1px] dark:bg-indigo-800/60 dark:text-indigo-100"
              >
                Понятно
              </button>
            </div>
          </div>
        )}
        {!isAuthenticated && (
          <div className="flex items-center justify-between gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800 shadow-sm dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-100">
            <p>Войдите, чтобы закрепить историю за аккаунтом и продолжать с любого устройства.</p>
            <a
              href="/auth"
              className="rounded-full bg-white/70 px-3 py-1 text-[11px] font-semibold text-amber-800 shadow-sm transition hover:-translate-y-[1px] dark:bg-amber-900 dark:text-amber-50"
            >
              Войти
            </a>
          </div>
        )}
      </div>

      {alerts.length > 0 && (
        <div className="mb-3 grid gap-2">
          {alerts.map((alert) => {
            const remaining = alert.minutes_left ?? 0;
            return (
              <div
                key={`${alert.booking_id}-${alert.type}`}
                className="flex items-center justify-between gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 shadow-sm dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-100"
              >
                <div className="flex items-center gap-2">
                  <ExclamationTriangleIcon className="h-4 w-4" />
                  <p>
                    {alert.type === 'booking_expiring'
                      ? `Бронь ${alert.spot || ''} заканчивается через ~${remaining} мин.`
                      : 'Обратите внимание на сессию парковки.'}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {sessions.length > 0 && (
        <div className="mb-4 space-y-2 rounded-3xl border border-[var(--border-subtle)]/70 bg-white/80 p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold text-[var(--text-primary)]">Активные сессии парковки</p>
            <button
              className="text-xs font-semibold text-[var(--text-muted)] underline decoration-dotted underline-offset-4"
              onClick={() => void fetchSessions()}
            >
              Обновить
            </button>
          </div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {sessions.map((session) => {
              const remaining = computeRemaining(session);
              const minutes = Math.max(0, Math.floor(remaining / 60));
              const isExpiring = minutes <= 15;
              return (
                <div
                  key={session.id}
                  className="flex flex-col gap-2 rounded-2xl border border-[var(--border-subtle)]/80 bg-[var(--bg-elevated)] p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900/70"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-[var(--text-primary)]">
                        {session.spot_name} · {session.lot_name}
                      </p>
                      <p className="text-[11px] text-[var(--text-muted)]">Статус: {session.status}</p>
                    </div>
                    <span
                      className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                        isExpiring
                          ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-100'
                          : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-100'
                      }`}
                    >
                      ~{minutes} мин
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      disabled={isLoading || actionRunning === session.id}
                      onClick={() => void handleAction({ type: 'booking_extend', booking_id: session.id, extend_minutes: 30 })}
                      className="rounded-full border border-[var(--border-subtle)]/70 bg-white px-3 py-1 text-xs font-semibold text-[var(--text-primary)] shadow-sm transition hover:-translate-y-[1px] dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 disabled:opacity-50"
                    >
                      +30 мин
                    </button>
                    <button
                      disabled={isLoading || actionRunning === session.id}
                      onClick={() => void handleAction({ type: 'booking_stop', booking_id: session.id })}
                      className="rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-red-700 shadow-sm transition hover:-translate-y-[1px] dark:border-red-800 dark:bg-red-950/40 dark:text-red-100 disabled:opacity-50"
                    >
                      Завершить
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}


      <div className="grid h-full grid-cols-1 gap-4 lg:grid-cols-[320px,1fr]">
        <div className="hidden lg:block">
          <ConversationList
            conversations={conversations}
            activeId={activeConversationId}
            onSelect={handleSelectConversation}
            onCreate={handleCreate}
            onRename={handleRename}
            onDelete={handleDelete}
          />
        </div>
        <div className="flex flex-col overflow-hidden rounded-[22px] border border-[var(--border-subtle)]/80 bg-[var(--bg-elevated)] shadow-[0_16px_36px_rgba(15,23,42,0.08)] backdrop-blur dark:border-slate-800/70 dark:bg-slate-900/70">
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6">
            {bookingActions.length > 0 && (
              <div className="rounded-2xl border border-[var(--border-subtle)]/70 bg-white/80 p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Быстрые действия</p>
                <div className="flex flex-wrap gap-2">
                  {bookingActions.map((action, idx) => {
                    const key = action.booking_id || action.spot_id || `${action.type}-${idx}`;
                    return (
                      <button
                        key={key}
                        disabled={isLoading || actionRunning === key}
                        onClick={() => void handleAction(action)}
                        className="rounded-full border border-[var(--border-subtle)]/70 bg-white px-3 py-2 text-xs font-semibold text-[var(--text-primary)] shadow-sm transition hover:-translate-y-[1px] dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 disabled:opacity-50"
                      >
                        {actionLabel(action)}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            {currentConversation && currentConversation.messages.length <= 1 ? (
              <div className="flex flex-col gap-3 rounded-2xl border border-dashed border-slate-200 bg-white/60 p-4 text-sm text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-200">
                <p className="font-semibold text-slate-900 dark:text-slate-50">Начните новый диалог</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Добавьте первый запрос или выберите одну из заготовок. История сохранится локально и привяжется к вашему профилю.
                </p>
                <div className="flex flex-wrap gap-2">
                  {FAVORITE_PROMPTS.slice(0, 3).map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => handlePrefill(prompt)}
                      className="rounded-full border border-slate-200/70 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:-translate-y-[1px] hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-800 dark:bg-slate-800/80 dark:text-slate-200"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              currentConversation?.messages.map((message) => (
                <MessageBubble key={message.id} message={message} isLoading={isLoading} onRegenerate={handleRegenerate} />
              ))
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="sticky bottom-0 border-t border-[var(--border-subtle)]/80 bg-gradient-to-r from-white/95 via-[var(--bg-elevated)] to-white/95 p-4 backdrop-blur dark:border-slate-800 dark:from-slate-900/90 dark:via-slate-900 dark:to-slate-900/90">
            <div className="flex flex-col gap-2">
              <label htmlFor="chat-input" className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Спросить ассистента
              </label>
              {!isAuthenticated && (
                <p className="text-[11px] text-amber-700 dark:text-amber-200">
                  Гостевой режим: история сохраняется только в этом браузере. Войдите, чтобы привязать её к профилю.
                </p>
              )}
              {errorMessage && (
                <div className="flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 shadow-sm dark:border-red-900 dark:bg-red-950/40 dark:text-red-100">
                  <div className="flex items-start gap-2">
                    <ExclamationTriangleIcon className="mt-0.5 h-4 w-4" />
                    <p>{errorMessage}</p>
                  </div>
                  <button
                    onClick={() => setErrorMessage(null)}
                    className="rounded-md px-2 py-1 text-[11px] font-semibold text-red-700 transition hover:bg-red-100 dark:text-red-50 dark:hover:bg-red-900/60"
                    aria-label="Dismiss error"
                  >
                    Dismiss
                  </button>
                </div>
              )}
              <div className="flex flex-col gap-3 rounded-2xl border border-slate-200/70 bg-white/70 p-3 shadow-sm transition focus-within:border-indigo-200 focus-within:ring-1 focus-within:ring-indigo-200 dark:border-slate-800/60 dark:bg-slate-900/70 dark:focus-within:border-indigo-500/50 dark:focus-within:ring-indigo-500/50">
                <textarea
                  id="chat-input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={3}
                  className="flex-1 resize-none border-none bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-slate-100"
                  placeholder="Как оптимизировать тарифы на выходные или при событиях?"
                />
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                    <span>Enter — отправить • Shift+Enter — перенос строки</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleClear}
                      className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:-translate-y-[1px] hover:border-indigo-200 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                    >
                      Очистить
                    </button>
                    <button
                      onClick={() => void handleSend()}
                      disabled={sendDisabled}
                      className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-500 to-blue-500 px-4 py-2 text-sm font-semibold text-white shadow-md transition hover:-translate-y-[1px] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <PaperAirplaneIcon className="h-5 w-5" />
                      Отправить
                    </button>
                  </div>
                </div>
              </div>
              {isLoading && (
                <p className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-500" /> Запрашиваем ассистента…
                </p>
              )}
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
              onSelect={handleSelectConversation}
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
  isLoading,
  onRegenerate
}: {
  message: MessageWithId;
  isLoading: boolean;
  onRegenerate?: (id: string) => void;
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
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    if (!message.content) return;
    navigator.clipboard
      ?.writeText(message.content)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => setCopied(false));
  }, [message.content]);

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={bubbleClass}>
        <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          <span className="inline-flex items-center rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700 dark:bg-slate-700 dark:text-slate-200">
            {isUser ? 'You' : 'AI'}
          </span>
          <span className="text-[10px] text-slate-500 dark:text-slate-400">{timestamp}</span>
        </div>
        {!isUser && message.content && (
          <div className="absolute -right-3 -top-3 flex items-center gap-1">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 rounded-full border border-[var(--border-subtle)]/70 bg-white px-2 py-1 text-[11px] font-semibold text-[var(--text-muted)] shadow-sm transition hover:-translate-y-[1px] hover:text-[var(--text-primary)] dark:bg-slate-900"
              aria-label="Copy message"
            >
              <ClipboardIcon className="h-3.5 w-3.5" />
              {copied ? 'Скопировано' : 'Копия'}
            </button>
            {onRegenerate && (
              <button
                onClick={() => onRegenerate(message.id)}
                className="flex items-center gap-1 rounded-full border border-[var(--border-subtle)]/70 bg-white px-2 py-1 text-[11px] font-semibold text-[var(--text-muted)] shadow-sm transition hover:-translate-y-[1px] hover:text-[var(--text-primary)] dark:bg-slate-900"
                aria-label="Regenerate"
              >
                <ArrowPathIcon className="h-3.5 w-3.5" />
                Повторить
              </button>
            )}
          </div>
        )}
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
