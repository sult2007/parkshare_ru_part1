import type { NextRequest } from 'next/server';
import { streamChat, type LLMMessage } from '@/lib/llmClient';

export const runtime = 'nodejs';

export async function POST(req: NextRequest) {
  let payload: { messages?: LLMMessage[]; stream?: boolean };

  try {
    payload = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON body' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const messages = payload.messages;

  if (!messages || !Array.isArray(messages) || messages.length === 0) {
    return new Response(JSON.stringify({ error: 'No messages provided' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const stream = await streamChat(messages, { stream: payload.stream !== false });

  return new Response(stream, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' }
  });
}
