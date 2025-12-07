import { streamChatFromApi } from '@/lib/chatClient';
import type { ChatMessage } from '@/lib/aiProvider';

describe('streamChatFromApi', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
  });

  it('posts chat messages and forwards reply to callback', async () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi!' }
    ];

    const mockFetch = jest.spyOn(global, 'fetch' as any).mockResolvedValue(
      new Response(JSON.stringify({ reply: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );

    const onChunk = jest.fn();

    await streamChatFromApi(messages, { onChunk });

    expect(mockFetch).toHaveBeenCalled();
    const requestInit = (mockFetch.mock.calls[0] as any)[1];
    expect(requestInit.method).toBe('POST');
    expect(onChunk).toHaveBeenCalledWith('ok');
  });

  it('throws when the API response is not ok', async () => {
    jest.spyOn(global, 'fetch' as any).mockResolvedValue(new Response(null, { status: 500, statusText: 'err' }));

    await expect(streamChatFromApi([{ role: 'user', content: 'test' }])).rejects.toThrow();
  });
});
