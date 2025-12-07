export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';

export interface ApiError extends Error {
  status?: number;
  payload?: unknown;
}

export interface ApiRequestOptions<TBody = unknown> {
  method?: HttpMethod;
  body?: TBody;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  credentials?: RequestCredentials;
  retries?: number;
  refreshOn401?: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api/v1';

async function parseError(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    try {
      payload = await response.text();
    } catch {
      payload = null;
    }
  }
  const error: ApiError = new Error((payload as any)?.detail || response.statusText || 'API error');
  error.status = response.status;
  error.payload = payload;
  return error;
}

async function refreshTokens() {
  const refreshUrl = `${API_BASE}/auth/token/refresh/`;
  const resp = await fetch(refreshUrl, { method: 'POST', credentials: 'include' });
  if (!resp.ok) {
    throw await parseError(resp);
  }
  return resp.json();
}

export async function apiRequest<TResponse = unknown, TBody = unknown>(
  endpoint: string,
  options: ApiRequestOptions<TBody> = {},
  attempt = 0
): Promise<TResponse> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const { method = 'GET', body, headers, signal, refreshOn401 = true } = options;
  const retries = options.retries ?? 1;

  let resp: Response;

  try {
    resp = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(headers || {})
      },
      body: body ? JSON.stringify(body) : undefined,
      credentials: options.credentials || 'include',
      signal
    });
  } catch (error) {
    if (attempt < retries) {
      return apiRequest(endpoint, options, attempt + 1);
    }
    throw error;
  }

  if (resp.status === 401 && refreshOn401 && attempt <= retries) {
    try {
      await refreshTokens();
      return apiRequest(endpoint, { ...options, refreshOn401: false }, attempt + 1);
    } catch (refreshError) {
      throw refreshError;
    }
  }

  if (!resp.ok) {
    throw await parseError(resp);
  }

  const contentType = resp.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return (await resp.json()) as TResponse;
  }
  return (await resp.text()) as unknown as TResponse;
}

export * from './apiTypes';
