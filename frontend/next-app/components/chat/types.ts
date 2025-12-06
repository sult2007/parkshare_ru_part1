import { ChatMessage } from '@/lib/aiProvider';

export interface MessageWithId extends ChatMessage {
  id: string;
  createdAt: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: MessageWithId[];
  updatedAt: number;
}
