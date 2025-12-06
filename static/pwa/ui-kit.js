import { registerPushSubscription } from './api-client.js';
import { setConnectionStatus, subscribe } from './state-store.js';

export function initPushUI() {
  const toggle = document.querySelector('[data-push-optin]');
  if (!toggle || !('serviceWorker' in navigator) || !('PushManager' in window)) return;
  toggle.addEventListener('click', async () => {
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') return;
      const reg = await navigator.serviceWorker.ready;
      const subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: window.PARKSHARE_VAPID_KEY || undefined,
      });
      await registerPushSubscription(subscription.toJSON());
      toggle.setAttribute('disabled', 'disabled');
      toggle.textContent = 'Уведомления включены';
    } catch (err) {
      console.warn('[PWA] push subscribe failed', err);
    }
  });
}

export function initConnectionBadge() {
  const badge = document.querySelector('[data-connection-indicator]');
  if (!badge) return;
  subscribe((state) => {
    if (state.isOnline) {
      badge.textContent = 'Онлайн';
      badge.classList.remove('ps-badge-offline');
    } else {
      badge.textContent = 'Оффлайн';
      badge.classList.add('ps-badge-offline');
    }
  });
  window.addEventListener('online', () => setConnectionStatus(true));
  window.addEventListener('offline', () => setConnectionStatus(false));
}
