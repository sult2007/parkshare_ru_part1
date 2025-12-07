import { apiRequest } from './apiClient';

export type AuthUser = {
  id: string;
  email?: string;
  phone?: string;
  name?: string;
  avatarUrl?: string;
  provider?: string;
};

export type AuthResponse = {
  success?: boolean;
  message?: string;
  user?: AuthUser;
  data?: unknown;
  mfa_required?: boolean;
  mfa_method?: string;
  mfa_channel?: string | null;
};

export async function requestOtp(identifier: string) {
  if (!identifier) throw new Error('Введите номер телефона или email');
  return apiRequest<AuthResponse>('/auth/otp/request/', { method: 'POST', body: { identifier, purpose: 'login' } });
}

export async function verifyOtp(identifier: string, code: string) {
  if (!identifier || !code) throw new Error('Введите контакт и код');
  return apiRequest<AuthResponse>('/auth/otp/verify/', {
    method: 'POST',
    body: { identifier, code, purpose: 'login' }
  });
}

export async function loginWithEmailPassword(identifier: string, password: string) {
  if (!identifier || !password) throw new Error('Нужны логин/email/телефон и пароль');
  return apiRequest<AuthResponse>('/auth/token/', { method: 'POST', body: { identifier, password } });
}

export async function registerWithEmailPassword(email: string, password: string, name?: string) {
  if (!email || !password) throw new Error('Укажите почту и пароль');
  return apiRequest<AuthResponse>('/auth/register/', { method: 'POST', body: { email, password, name } });
}

export async function logout() {
  return apiRequest<AuthResponse>('/auth/logout/', { method: 'POST' });
}

export async function verifyMfa(code: string) {
  if (!code) throw new Error('Введите код MFA');
  return apiRequest<AuthResponse>('/auth/mfa/verify/', { method: 'POST', body: { code } });
}

export async function getCurrentUser() {
  try {
    const data = await apiRequest<AuthUser>('/accounts/users/me/', { method: 'GET' });
    return data ?? null;
  } catch {
    return null;
  }
}

function buildOAuthUrl(provider: 'vk' | 'yandex' | 'google') {
  const base = process.env.NEXT_PUBLIC_AUTH_API_URL || process.env.NEXT_PUBLIC_AUTH_API_BASE || '/api';
  const returnTo = encodeURIComponent(typeof window !== 'undefined' ? window.location.href : '/');
  return `${base}/auth/oauth/${provider}/start/?next=${returnTo}`;
}

export function startOAuth(provider: 'vk' | 'yandex' | 'google') {
  const url = buildOAuthUrl(provider);
  window.location.href = url;
}
