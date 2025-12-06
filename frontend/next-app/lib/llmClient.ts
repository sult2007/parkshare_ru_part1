import type { ReadableStream } from 'stream/web';

export type LLMMessage = {
  role: 'user' | 'assistant' | 'system';
  content: string;
};

export type LLMProvider = 'openai' | 'proxy' | 'custom';

export interface LLMClientConfig {
  provider: LLMProvider;
  apiUrl: string;
  apiKey?: string;
  model?: string;
  authHeader?: string;
  authScheme?: string;
}

const encoder = new TextEncoder();

function fallbackStream(message: string) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(message));
      controller.close();
    }
  });
}

function resolveConfig(): LLMClientConfig {
  return {
    provider: (process.env.LLM_PROVIDER as LLMProvider) || 'openai',
    apiUrl: process.env.LLM_API_URL || 'https://api.openai.com/v1/chat/completions',
    apiKey: process.env.LLM_API_KEY || process.env.OPENAI_API_KEY,
    model: process.env.LLM_MODEL || 'gpt-4o-mini',
    authHeader: process.env.LLM_AUTH_HEADER || 'Authorization',
    authScheme: process.env.LLM_AUTH_SCHEME || 'Bearer'
  };
}

async function createRequest(messages: LLMMessage[], stream: boolean, signal?: AbortSignal): Promise<Response> {
  const config = resolveConfig();

  if (!config.apiUrl) {
    throw new Error('LLM_API_URL is not configured');
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  };

  if (config.apiKey) {
    headers[config.authHeader || 'Authorization'] = `${config.authScheme || 'Bearer'} ${config.apiKey}`.trim();
  }

  const body = {
    model: config.model,
    messages,
    stream
  };

  return fetch(config.apiUrl, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal
  });
}

export async function streamChat(messages: LLMMessage[], { signal, stream = true }: { signal?: AbortSignal; stream?: boolean } = {}) {
  if (!messages || !Array.isArray(messages) || messages.length === 0) {
    return fallbackStream('No messages provided to LLM.');
  }

  try {
    const response = await createRequest(messages, stream, signal);

    if (!response.ok || !response.body) {
      const errorText = await response.text();
      return fallbackStream(errorText || 'The LLM provider responded with an error.');
    }

    if (!stream) {
      // Non-streaming: return one chunk with the final message.
      const result = await response.json();
      const content =
        result?.choices?.[0]?.message?.content ||
        result?.message ||
        'The LLM provider did not return a message.';
      return fallbackStream(content);
    }

    const decoder = new TextDecoder();
    const reader = response.body.getReader();

    return new ReadableStream<Uint8Array>({
      async pull(controller) {
        const { done, value } = await reader.read();
        if (done) {
          controller.close();
          return;
        }

        const textChunk = decoder.decode(value, { stream: true });
        const lines = textChunk
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean);

        for (const line of lines) {
          const data = line.startsWith('data:') ? line.replace('data:', '').trim() : line;
          if (data === '[DONE]') {
            controller.close();
            return;
          }

          try {
            const payload = JSON.parse(data) as { choices?: Array<{ delta?: { content?: string } }> };
            const token = payload.choices?.[0]?.delta?.content;
            if (token) {
              controller.enqueue(encoder.encode(token));
              continue;
            }
          } catch {
            // Not JSON or not OpenAI-shaped – stream raw text.
          }

          if (data) {
            controller.enqueue(encoder.encode(data));
          }
        }
      },
      cancel() {
        reader.cancel().catch(() => undefined);
      }
    });
  } catch (error) {
    console.error('LLM streaming failed', error);
    return fallbackStream('LLM is unreachable. Check configuration or network.');
  }
}

export const isLLMConfigured = () => Boolean(process.env.LLM_API_URL || process.env.OPENAI_API_KEY || process.env.LLM_API_KEY);
