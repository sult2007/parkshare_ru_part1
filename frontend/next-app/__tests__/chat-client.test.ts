import { streamChatFromApi } from '@/lib/chatClient';
import type { ChatMessage } from '@/lib/aiProvider';

const encoder = new TextEncoder();

function streamFromStrings(chunks: string[]) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    }
  });
}

describe('streamChatFromApi', () => {
  it('posts chat messages and streams tokens to callback', async () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi!' }
    ];

    const mockFetch = jest.fn().mockResolvedValue(
      new Response(streamFromStrings(['Hello', ' world']), {
        status: 200,
        headers: { 'Content-Type': 'text/plain' }
      })
    );

    const onChunk = jest.fn();

    await streamChatFromApi(messages, { fetcher: mockFetch, onChunk });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/chat',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
    );

    const body = mockFetch.mock.calls[0][1]?.body as string;
    expect(JSON.parse(body).messages).toEqual(messages);

    expect(onChunk).toHaveBeenCalledWith('Hello');
    expect(onChunk).toHaveBeenCalledWith(' world');
  });

  it('throws when the API response is not ok', async () => {
    const mockFetch = jest.fn().mockResolvedValue(new Response(null, { status: 500 }));

    await expect(streamChatFromApi([{ role: 'user', content: 'test' }], { fetcher: mockFetch })).rejects.toThrow(
      'Failed to reach chat API'
    );
  });
});
