import { registerPushSubscription } from './api-client.js';
import { setConnectionStatus, subscribe } from './state-store.js';

export function createBadge(text, tone = 'info') {
  const span = document.createElement('span');
  span.className = `ps-badge ps-badge-${tone}`;
  span.textContent = text;
  return span;
}

export function renderSkeletonCards(container, count = 3) {
  if (!container) return;
  container.innerHTML = '';
  for (let i = 0; i < count; i += 1) {
    const card = document.createElement('article');
    card.className = 'ps-card ps-card--spot ps-card--skeleton';
    card.innerHTML = `
      <div class="ps-skeleton-line ps-skeleton-line--lg"></div>
      <div class="ps-skeleton-line"></div>
      <div class="ps-skeleton-line ps-skeleton-line--short"></div>
    `;
    container.appendChild(card);
  }
}

export function renderSpotCard(spot, { favorite, onFavorite, aiHint } = {}) {
  const card = document.createElement('article');
  card.className = 'ps-card ps-card--spot';
  card.dataset.spotId = spot.id;
  const badge = aiHint
    ? `<span class="ps-badge ps-badge-success">${aiHint.label || 'AI'}</span>`
    : '';
  const priceHint = aiHint?.reason ? `<div class="ps-card-line ps-card-line--muted">${aiHint.reason}</div>` : '';
  card.innerHTML = `
    <div class="ps-card-header">
      <div class="ps-card-title">${spot.lot?.city || ''} ${spot.lot?.name || ''} — ${spot.name}</div>
      <button class="ps-icon-btn" type="button" aria-label="В избранное" data-fav-toggle>
        ${favorite ? '★' : '☆'}
      </button>
    </div>
    <div class="ps-card-body">
      <div class="ps-card-line">от ${spot.hourly_price} ₽/час ${badge}</div>
      <div class="ps-card-line ps-card-line--muted">${spot.lot?.address || 'Адрес уточняется'}</div>
      ${priceHint}
    </div>
  `;
  if (onFavorite) {
    card.querySelector('[data-fav-toggle]')?.addEventListener('click', onFavorite);
  }
  return card;
}

export function initLazyMedia() {
  document.querySelectorAll('img[loading="lazy"], source[loading="lazy"]').forEach((node) => {
    node.decoding = 'async';
  });
  const lazyNodes = document.querySelectorAll('[data-lazy-src]');
  if (!lazyNodes.length) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const el = entry.target;
        el.src = el.dataset.lazySrc;
        observer.unobserve(el);
      }
    });
  });
  lazyNodes.forEach((node) => observer.observe(node));
}

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
