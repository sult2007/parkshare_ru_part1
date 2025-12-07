import type { NextRequest } from 'next/server';

export const runtime = 'nodejs';

export async function POST(req: NextRequest) {
  let body: any = {};
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON body' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE || process.env.API_BASE || 'http://localhost:8000/api/v1';
  const endpoint = `${apiBase.replace(/\/$/, '')}/assistant/chat/`;
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include'
  });

  const text = await resp.text();
  return new Response(text, {
    status: resp.status,
    headers: {
      'Content-Type': resp.headers.get('content-type') || 'application/json',
      'Cache-Control': 'no-store'
    }
  });
}
