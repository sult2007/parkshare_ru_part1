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
  verifyMfa,
  verifyOtp
} from '@/lib/authClient';
import { clearUserSecure, getUserSecure, saveUserSecure } from '@/lib/authStorage';

type MfaChallenge = {
  method: string | null;
  channel?: string | null;
};

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  mfaChallenge: MfaChallenge | null;
  loginWithEmail: (email: string, password: string) => Promise<AuthUser | null>;
  registerWithEmail: (email: string, password: string, name?: string) => Promise<AuthUser | null>;
  requestPhoneOtp: (phone: string) => Promise<void>;
  verifyPhoneOtp: (phone: string, code: string) => Promise<AuthUser | null>;
  verifyMfaCode: (code: string) => Promise<AuthUser | null>;
  loginWithVK: () => void;
  loginWithYandex: () => void;
  clearMfaChallenge: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [mfaChallenge, setMfaChallenge] = useState<MfaChallenge | null>(null);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const saved = await getUserSecure();
        if (saved) {
          setUser(saved);
          setLoading(false);
          return;
        }
        const serverUser = await getCurrentUser();
        if (serverUser) {
          setUser(serverUser);
          await saveUserSecure(serverUser);
        }
      } catch (error) {
        console.warn('Auth bootstrap failed', error);
      } finally {
        setLoading(false);
      }
    };

    void bootstrap();
  }, []);

  const persistUser = useCallback(async (nextUser: AuthUser | null) => {
    setUser(nextUser);
    if (nextUser) {
      await saveUserSecure(nextUser);
    } else {
      clearUserSecure();
    }
    setMfaChallenge(null);
  }, []);

  const loginWithEmail = useCallback(
    async (email: string, password: string) => {
      const response = await loginWithEmailPassword(email, password);
      if (response.mfa_required) {
        setMfaChallenge({ method: response.mfa_method ?? 'totp', channel: response.mfa_channel ?? null });
        return null;
      }
      if (response.user) {
        await persistUser(response.user);
        return response.user;
      }
      return null;
    },
    [persistUser]
  );

  const registerWithEmail = useCallback(
    async (email: string, password: string, name?: string) => {
      const response = await registerWithEmailPassword(email, password, name);
      if (response.mfa_required) {
        setMfaChallenge({ method: response.mfa_method ?? 'totp', channel: response.mfa_channel ?? null });
        return null;
      }
      if (response.user) {
        await persistUser(response.user);
        return response.user;
      }
      return null;
    },
    [persistUser]
  );

  const requestPhoneOtp = useCallback(async (phone: string) => {
    await requestOtp(phone);
  }, []);

  const verifyPhoneOtp = useCallback(
    async (phone: string, code: string) => {
      const response = await verifyOtp(phone, code);
      if (response.mfa_required) {
        setMfaChallenge({ method: response.mfa_method ?? 'totp', channel: response.mfa_channel ?? null });
        return null;
      }
      if (response.user) {
        await persistUser(response.user);
        return response.user;
      }
      return null;
    },
    [persistUser]
  );

  const verifyMfaCode = useCallback(
    async (code: string) => {
      const response = await verifyMfa(code);
      if (response.user) {
        await persistUser(response.user);
        return response.user;
      }
      return null;
    },
    [persistUser]
  );

  const loginWithVK = useCallback(() => startOAuth('vk'), []);
  const loginWithYandex = useCallback(() => startOAuth('yandex'), []);

  const logout = useCallback(async () => {
    await apiLogout();
    await persistUser(null);
  }, [persistUser]);

  const value = useMemo(
    () => ({
      user,
      loading,
      mfaChallenge,
      loginWithEmail,
      registerWithEmail,
      requestPhoneOtp,
      verifyPhoneOtp,
      verifyMfaCode,
      loginWithVK,
      loginWithYandex,
      clearMfaChallenge: () => setMfaChallenge(null),
      logout
    }),
    [
      user,
      loading,
      mfaChallenge,
      loginWithEmail,
      registerWithEmail,
      requestPhoneOtp,
      verifyPhoneOtp,
      verifyMfaCode,
      loginWithVK,
      loginWithYandex,
      logout
    ]
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
