'use client';

import { useMemo, useState, useEffect, useRef } from 'react';
import type React from 'react';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import rehypeHighlight from 'rehype-highlight';
import { ChatMessage } from '@/lib/aiProvider';

interface MessageWithId extends ChatMessage {
  id: string;
}

export function ChatPanel() {
  const [messages, setMessages] = useState<MessageWithId[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Hi! I am your ParkShare AI concierge. Ask me about occupancy, pricing, or customer journeys.'
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: MessageWithId = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim()
    };

    const updatedHistory = [...messages, userMessage].slice(-12);
    setMessages(updatedHistory);
    setInput('');
    setIsLoading(true);

    const assistantMessage: MessageWithId = { id: crypto.randomUUID(), role: 'assistant', content: '' };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ messages: updatedHistory.map(({ id, ...rest }) => rest) })
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
        setMessages((prev) =>
          prev.map((msg) => (msg.id === assistantMessage.id ? { ...msg, content: msg.content + textChunk } : msg))
        );
      }
    } catch (error) {
      console.error(error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                content: 'Something went wrong reaching the AI. Please confirm your API key and try again.'
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const sendDisabled = isLoading || !input.trim();

  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        <div ref={chatEndRef} />
      </div>
      <div className="border-t border-slate-200 bg-slate-50/80 p-4 dark:border-slate-800 dark:bg-slate-800/40">
        <div className="flex flex-col gap-2">
          <label htmlFor="chat-input" className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Ask the concierge
          </label>
          <div className="flex items-end gap-3">
            <textarea
              id="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={3}
              className="flex-1 resize-none"
              placeholder="How can I optimize pricing for weekend events?"
            />
            <button
              onClick={handleSend}
              disabled={sendDisabled}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-white shadow disabled:cursor-not-allowed disabled:bg-indigo-300"
            >
              <PaperAirplaneIcon className="h-5 w-5" />
              Send
            </button>
          </div>
          {isLoading && <p className="text-xs text-slate-500">Streaming response…</p>}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: MessageWithId }) {
  const isUser = message.role === 'user';
  const bubbleClass = useMemo(
    () =>
      `max-w-3xl rounded-2xl px-4 py-3 text-sm shadow-sm ${
        isUser
          ? 'bg-indigo-600 text-white ml-auto' // align right for users
          : 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-50'
      }`,
    [isUser]
  );

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={bubbleClass}>
        {isUser ? (
          <p className="whitespace-pre-line">{message.content}</p>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize, rehypeHighlight]} className="prose prose-sm dark:prose-invert">
            {message.content || '…'}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}
