export type AuthUser = {
  id: string;
  email?: string;
  phone?: string;
  name?: string;
  avatarUrl?: string;
  provider?: string;
};

export type AuthResponse = {
  success: boolean;
  message?: string;
  user?: AuthUser;
  data?: unknown;
  mfa_required?: boolean;
  mfa_method?: string;
  mfa_channel?: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_AUTH_API_URL || process.env.NEXT_PUBLIC_AUTH_API_BASE;

async function request<T = AuthResponse>(endpoint: string, body?: Record<string, unknown>, init?: RequestInit): Promise<T> {
  if (!API_BASE) {
    return Promise.resolve({
      success: true,
      message: 'DEMO: Backend URL не задан, имитируем успешный ответ.',
      user: {
        id: 'demo-user',
        email: body && 'email' in body ? (body.email as string) : undefined,
        phone: body && 'phone' in body ? (body.phone as string) : undefined,
        name: 'Demo User',
        provider: 'demo'
      },
      mfa_required: false
    } as T);
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: body ? JSON.stringify(body) : undefined,
    ...init
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || 'Auth request failed');
  }

  return response.json();
}

export async function requestOtp(phone: string) {
  if (!phone) throw new Error('Введите номер телефона');
  return request<AuthResponse>('/auth/otp/request', { phone });
}

export async function verifyOtp(phone: string, code: string) {
  if (!phone || !code) throw new Error('Введите телефон и код');
  return request<AuthResponse>('/auth/otp/verify', { phone, code });
}

export async function loginWithEmailPassword(email: string, password: string) {
  if (!email || !password) throw new Error('Нужны почта и пароль');
  return request<AuthResponse>('/auth/email/login', { email, password });
}

export async function registerWithEmailPassword(email: string, password: string, name?: string) {
  if (!email || !password) throw new Error('Укажите почту и пароль');
  return request<AuthResponse>('/auth/email/register', { email, password, name });
}

export async function logout() {
  if (!API_BASE) return { success: true, message: 'DEMO: лог-аут выполнен локально.' };
  return request<AuthResponse>('/auth/logout');
}

export async function verifyMfa(code: string) {
  if (!code) throw new Error('Введите код MFA');
  return request<AuthResponse>('/auth/mfa/verify', { code });
}

export async function getCurrentUser() {
  if (!API_BASE) return null;
  const response = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' });
  if (!response.ok) return null;
  const data = (await response.json()) as AuthResponse;
  return data.user ?? null;
}

function buildOAuthUrl(provider: 'vk' | 'yandex') {
  const redirectUriParam =
    provider === 'vk'
      ? process.env.NEXT_PUBLIC_VK_REDIRECT_URI
      : process.env.NEXT_PUBLIC_YANDEX_REDIRECT_URI;
  const clientIdParam =
    provider === 'vk' ? process.env.NEXT_PUBLIC_VK_CLIENT_ID : process.env.NEXT_PUBLIC_YANDEX_CLIENT_ID;

  if (clientIdParam && redirectUriParam) {
    const redirect = encodeURIComponent(redirectUriParam);
    return provider === 'vk'
      ? `https://id.vk.com/authorize?client_id=${clientIdParam}&redirect_uri=${redirect}&response_type=code`
      : `https://oauth.yandex.ru/authorize?response_type=code&client_id=${clientIdParam}&redirect_uri=${redirect}`;
  }

  const base = API_BASE || '';
  const returnTo = encodeURIComponent(typeof window !== 'undefined' ? window.location.href : '/');
  return `${base}/auth/oauth/${provider}?redirect_uri=${returnTo}`;
}

export function startOAuth(provider: 'vk' | 'yandex' | 'google') {
  if (provider === 'google') {
    const base = API_BASE || '';
    const redirect = encodeURIComponent(typeof window !== 'undefined' ? window.location.href : '/');
    window.location.href = `${base}/auth/oauth/google?redirect_uri=${redirect}`;
    return;
  }

  const url = buildOAuthUrl(provider);
  window.location.href = url;
}
