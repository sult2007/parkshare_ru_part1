import { ChatMessage } from './aiProvider';

type StreamChatOptions = {
  fetcher?: typeof fetch;
  onChunk?: (chunk: string) => void;
  signal?: AbortSignal;
};

export async function streamChatFromApi(messages: ChatMessage[], options: StreamChatOptions = {}) {
  const fetcher = options.fetcher ?? fetch;
  const response = await fetcher('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ messages, stream: true }),
    signal: options.signal
  });

  if (!response.ok || !response.body) {
    const errorText = await response.text();
    throw new Error(errorText || 'Failed to reach chat API');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const textChunk = decoder.decode(value, { stream: true });
    options.onChunk?.(textChunk);
  }
}
