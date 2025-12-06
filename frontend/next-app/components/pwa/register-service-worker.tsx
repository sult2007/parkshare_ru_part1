'use client';

import { useEffect } from 'react';

export function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') return;
    if (!('serviceWorker' in navigator)) return;

    const register = async () => {
      try {
        await navigator.serviceWorker.register('/service-worker.js');
        console.info('Service worker registered');
      } catch (error) {
        console.error('Failed to register service worker', error);
      }
    };

    register();
  }, []);

  return null;
}
