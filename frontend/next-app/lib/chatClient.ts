import { ChatMessage } from './aiProvider';
import { chatEnabled } from './featureFlags';
import { apiRequest, type AssistantResponse } from './apiClient';

type StreamChatOptions = {
  onChunk?: (chunk: string) => void;
  signal?: AbortSignal;
};

export async function streamChatFromApi(messages: ChatMessage[], options: StreamChatOptions = {}) {
  if (!chatEnabled) {
    throw new Error('AI chat is disabled');
  }

  const response = await apiRequest<AssistantResponse>('/assistant/chat/', {
    method: 'POST',
    body: { messages, structured: true },
    signal: options.signal
  });
  if (response.reply && options.onChunk) {
    options.onChunk(response.reply);
  }
  return response;
}
