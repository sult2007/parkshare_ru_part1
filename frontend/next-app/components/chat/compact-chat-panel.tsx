'use client';

import { ChatPanel } from './chat-panel';

export function CompactChatPanel() {
  // На будущее сюда можно будет передать пропсы для "урезанного" вида,
  // сейчас просто используем существующую панель.
  return <ChatPanel />;
}
