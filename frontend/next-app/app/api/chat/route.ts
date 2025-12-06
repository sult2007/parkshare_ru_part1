import { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';
import { streamChatResponse, ChatMessage } from '@/lib/aiProvider';

export const runtime = 'edge';

export async function POST(req: NextRequest) {
  const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });
  if (!token) {
    return new Response('Unauthorized', { status: 401 });
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
