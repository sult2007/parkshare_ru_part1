import { ChatMessage } from './aiProvider';

type StreamChatOptions = {
  fetcher?: typeof fetch;
  onChunk?: (chunk: string) => void;
};

export async function streamChatFromApi(messages: ChatMessage[], options: StreamChatOptions = {}) {
  const fetcher = options.fetcher ?? fetch;
  const response = await fetcher('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ messages })
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
    options.onChunk?.(textChunk);
  }
}
