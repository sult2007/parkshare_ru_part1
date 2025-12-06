'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  type AuthUser,
  getCurrentUser,
  loginWithEmailPassword,
  logout as apiLogout,
  registerWithEmailPassword,
  requestOtp,
  startOAuth,
  verifyOtp
} from '@/lib/authClient';

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  loginWithEmail: (email: string, password: string) => Promise<AuthUser | null>;
  registerWithEmail: (email: string, password: string, name?: string) => Promise<AuthUser | null>;
  requestPhoneOtp: (phone: string) => Promise<void>;
  verifyPhoneOtp: (phone: string, code: string) => Promise<AuthUser | null>;
  loginWithVK: () => void;
  loginWithYandex: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const STORAGE_KEY = 'parkshare_auth_user';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        if (typeof window !== 'undefined') {
          const saved = localStorage.getItem(STORAGE_KEY);
          if (saved) {
            setUser(JSON.parse(saved));
            setLoading(false);
            return;
          }
        }
        const serverUser = await getCurrentUser();
        if (serverUser) {
          setUser(serverUser);
          if (typeof window !== 'undefined') {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(serverUser));
          }
        }
      } catch (error) {
        console.warn('Auth bootstrap failed', error);
      } finally {
        setLoading(false);
      }
    };

    void bootstrap();
  }, []);

  const persistUser = useCallback((nextUser: AuthUser | null) => {
    setUser(nextUser);
    if (typeof window !== 'undefined') {
      if (nextUser) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(nextUser));
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
  }, []);

  const loginWithEmail = useCallback(async (email: string, password: string) => {
    const response = await loginWithEmailPassword(email, password);
    if (response.user) {
      persistUser(response.user);
      return response.user;
    }
    return null;
  }, [persistUser]);

  const registerWithEmail = useCallback(async (email: string, password: string, name?: string) => {
    const response = await registerWithEmailPassword(email, password, name);
    if (response.user) {
      persistUser(response.user);
      return response.user;
    }
    return null;
  }, [persistUser]);

  const requestPhoneOtp = useCallback(async (phone: string) => {
    await requestOtp(phone);
  }, []);

  const verifyPhoneOtp = useCallback(async (phone: string, code: string) => {
    const response = await verifyOtp(phone, code);
    if (response.user) {
      persistUser(response.user);
      return response.user;
    }
    return null;
  }, [persistUser]);

  const loginWithVK = useCallback(() => startOAuth('vk'), []);
  const loginWithYandex = useCallback(() => startOAuth('yandex'), []);

  const logout = useCallback(async () => {
    await apiLogout();
    persistUser(null);
  }, [persistUser]);

  const value = useMemo(
    () => ({
      user,
      loading,
      loginWithEmail,
      registerWithEmail,
      requestPhoneOtp,
      verifyPhoneOtp,
      loginWithVK,
      loginWithYandex,
      logout
    }),
    [user, loading, loginWithEmail, registerWithEmail, requestPhoneOtp, verifyPhoneOtp, loginWithVK, loginWithYandex, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuthContext must be used within AuthProvider');
  }
  return ctx;
}
