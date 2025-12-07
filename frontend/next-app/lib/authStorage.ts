import type { AuthUser } from './authClient';

const STORAGE_KEY = 'ps_secure_user';
const ENC_KEY = process.env.NEXT_PUBLIC_AUTH_ENC_KEY || '';

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function toBase64(buf: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buf)));
}

function fromBase64(value: string): Uint8Array {
  const bin = atob(value);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) {
    bytes[i] = bin.charCodeAt(i);
  }
  return bytes;
}

async function deriveKey() {
  if (!ENC_KEY || typeof window === 'undefined' || !window.crypto?.subtle) return null;
  const hash = await crypto.subtle.digest('SHA-256', encoder.encode(ENC_KEY));
  return crypto.subtle.importKey('raw', hash, 'AES-GCM', false, ['encrypt', 'decrypt']);
}

export async function saveUserSecure(user: AuthUser) {
  if (typeof window === 'undefined') return;
  const key = await deriveKey();
  if (!key) return;
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const payload = encoder.encode(JSON.stringify(user));
  try {
    const cipher = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, payload);
    localStorage.setItem(`${STORAGE_KEY}:iv`, toBase64(iv.buffer));
    localStorage.setItem(`${STORAGE_KEY}:data`, toBase64(cipher));
  } catch (error) {
    console.warn('Encrypt user failed', error);
  }
}

export async function getUserSecure(): Promise<AuthUser | null> {
  if (typeof window === 'undefined') return null;
  const ivRaw = localStorage.getItem(`${STORAGE_KEY}:iv`);
  const dataRaw = localStorage.getItem(`${STORAGE_KEY}:data`);
  if (!ivRaw || !dataRaw) return null;
  const key = await deriveKey();
  if (!key) return null;
  try {
    const iv = fromBase64(ivRaw);
    const cipher = fromBase64(dataRaw);
    const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, cipher);
    const text = decoder.decode(plain);
    return JSON.parse(text) as AuthUser;
  } catch (error) {
    console.warn('Decrypt user failed, cleaning storage', error);
    clearUserSecure();
    return null;
  }
}

export function clearUserSecure() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(`${STORAGE_KEY}:iv`);
  localStorage.removeItem(`${STORAGE_KEY}:data`);
}
