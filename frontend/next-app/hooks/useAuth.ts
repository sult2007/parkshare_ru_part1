'use client';

import { useMemo } from 'react';
import { useAuthContext } from '@/context/AuthContext';

export function useAuth() {
  const ctx = useAuthContext();

  return useMemo(
    () => ({
      ...ctx,
      isAuthenticated: Boolean(ctx.user)
    }),
    [ctx]
  );
}
