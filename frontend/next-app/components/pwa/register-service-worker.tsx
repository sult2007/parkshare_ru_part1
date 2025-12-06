'use client';

import { useEffect, useState } from 'react';

export function ServiceWorkerRegistrar() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') return;
    if (!('serviceWorker' in navigator)) return;

    const register = async () => {
      try {
        await navigator.serviceWorker.register('/service-worker.js');
        console.info('Service worker registered');
      } catch (error) {
        console.error('Failed to register service worker', error);
        setError('Offline mode is temporarily unavailable. We will retry soon.');
      }
    };

    register();
  }, []);

  if (!error) return null;

  return (
    <div className="fixed bottom-4 right-4 z-30 max-w-sm rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 shadow-md dark:border-amber-800 dark:bg-amber-950/70 dark:text-amber-100">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-amber-200 text-xs font-bold text-amber-800 dark:bg-amber-800 dark:text-amber-100">!</span>
        <div className="space-y-1">
          <p className="font-semibold">Offline caching issue</p>
          <p className="text-xs leading-relaxed">{error}</p>
        </div>
      </div>
    </div>
  );
}
