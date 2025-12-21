const chatFlag = process.env.NEXT_PUBLIC_ENABLE_AI_CHAT ?? process.env.ENABLE_AI_CHAT;
export const chatEnabled = chatFlag === 'true' || chatFlag === '1';
