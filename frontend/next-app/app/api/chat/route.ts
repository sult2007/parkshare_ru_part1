import { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';
import { streamChatResponse, ChatMessage } from '@/lib/aiProvider';

export const runtime = 'edge';

const RATE_LIMIT_WINDOW = 60_000;
const RATE_LIMIT_MAX = 20;
// Simple in-memory limiter per edge instance. For demo purposes only.
const rateBucket = new Map<string, { count: number; start: number }>();

function getClientKey(req: NextRequest, userId?: string | null) {
  if (userId) return `user:${userId}`;
  const forwardedFor = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim();
  return `ip:${forwardedFor || 'anonymous'}`;
}

function isRateLimited(key: string) {
  const now = Date.now();
  const entry = rateBucket.get(key);
  if (!entry || now - entry.start > RATE_LIMIT_WINDOW) {
    rateBucket.set(key, { count: 1, start: now });
    return false;
  }

  entry.count += 1;
  rateBucket.set(key, entry);
  return entry.count > RATE_LIMIT_MAX;
}

export async function POST(req: NextRequest) {
  const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });
  if (!token) {
    return new Response('Unauthorized', { status: 401 });
  }

  const key = getClientKey(req, token.sub);
  if (isRateLimited(key)) {
    return new Response('Rate limit exceeded. Please slow down and try again shortly.', {
      status: 429,
      headers: { 'Retry-After': '60' }
    });
  }

  let payload: { messages?: ChatMessage[] };
  try {
    payload = await req.json();
  } catch (error) {
    return new Response('Invalid JSON', { status: 400 });
  }

  const messages = payload.messages?.slice(-12) ?? [];
  if (!Array.isArray(messages) || messages.length === 0) {
    return new Response('No messages provided', { status: 400 });
  }

  const stream = await streamChatResponse(messages);

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8'
    }
  });
}
