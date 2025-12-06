export type ChatMessage = {
  role: 'user' | 'assistant' | 'system';
  content: string;
};

const encoder = new TextEncoder();

function fallbackStream(message: string) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(message));
      controller.close();
    }
  });
}

export async function streamChatResponse(messages: ChatMessage[]): Promise<ReadableStream<Uint8Array>> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return fallbackStream('AI is not configured. Please set OPENAI_API_KEY.');
  }

  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`
    },
    body: JSON.stringify({
      model: process.env.AI_MODEL || 'gpt-3.5-turbo',
      messages,
      stream: true
    })
  });

  if (!response.ok || !response.body) {
    return fallbackStream('The AI service is unavailable right now.');
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
        .filter((line) => line.startsWith('data:'));

      for (const line of lines) {
        const data = line.replace('data:', '').trim();
        if (data === '[DONE]') {
          controller.close();
          return;
        }
        try {
          const payload = JSON.parse(data) as { choices?: Array<{ delta?: { content?: string } }> };
          const token = payload.choices?.[0]?.delta?.content;
          if (token) {
            controller.enqueue(encoder.encode(token));
          }
        } catch (error) {
          console.error('Failed to parse AI chunk', error);
        }
      }
    }
  });
}
